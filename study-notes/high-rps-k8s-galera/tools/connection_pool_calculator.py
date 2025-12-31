#!/usr/bin/env python3
"""
OpenFGA + MariaDB Galera 連接池配置計算器
用於計算在特定 RPS 和資源限制下的最優連接池配置
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class RPSScenario:
    """RPS 場景參數"""
    target_rps: int
    avg_latency_ms: int  # 平均查詢延遲（毫秒）
    safety_factor: float  # 安全係數（1.2-2.0）
    pod_replicas: int  # Pod 副本數


@dataclass
class DatabaseConfig:
    """資料庫配置"""
    max_open_conns: int
    max_idle_conns: int
    conn_max_idle_time: str
    conn_max_lifetime: str
    min_connections_per_node: int  # 每個 Galera 節點的最小連接


def calculate_required_connections(scenario: RPSScenario) -> int:
    """
    計算達到目標 RPS 需要的總連接數
    
    公式: 需要連接數 = (RPS × 平均延遲 / 1000) × 安全係數
    """
    total_connections = (
        scenario.target_rps 
        * scenario.avg_latency_ms 
        / 1000 
        * scenario.safety_factor
    )
    return math.ceil(total_connections)


def calculate_per_pod_config(
    total_required_conns: int,
    pod_replicas: int,
    galera_nodes: int = 3
) -> Tuple[int, int]:
    """
    計算每個 Pod 的連接池配置
    
    返回: (MaxOpenConns, MaxIdleConns)
    """
    # 每個 Pod 的最大開放連接數
    max_open_per_pod = math.ceil(total_required_conns / pod_replicas)
    
    # 最大空閒連接數（建議為 MaxOpenConns 的 30-50%）
    max_idle_per_pod = math.ceil(max_open_per_pod * 0.4)
    
    return max_open_per_pod, max_idle_per_pod


def calculate_galera_max_connections(
    total_open_conns: int,
    galera_nodes: int = 3,
    buffer_percentage: float = 0.2
) -> int:
    """
    計算 MariaDB Galera max_connections 設置
    
    考慮:
    - OpenFGA 連接
    - 內部 Galera 通信連接
    - 備用緩衝（20%）
    """
    internal_connections = galera_nodes * 5  # 每個節點的內部連接
    buffer = math.ceil(total_open_conns * buffer_percentage)
    
    max_connections = total_open_conns + internal_connections + buffer
    return max(2000, max_connections)  # 至少 2000


def recommend_idle_and_lifetime() -> Dict[str, str]:
    """
    根據場景推薦 ConnMaxIdleTime 和 ConnMaxLifetime
    """
    return {
        "ConnMaxIdleTime": "60s",      # 60 秒後回收空閒連接
        "ConnMaxLifetime": "10m",      # 10 分鐘後強制更新連接
    }


def calculate_cpu_memory_resources(
    total_rps: int,
    avg_latency_ms: int,
    pod_replicas: int
) -> Dict[str, Dict[str, str]]:
    """
    根據 RPS 和延遲計算 CPU 和記憶體資源需求
    """
    # 簡化模型：每 1000 RPS 需要 500m CPU
    rps_per_pod = total_rps / pod_replicas
    
    cpu_request_m = math.ceil((rps_per_pod / 1000) * 500)
    cpu_limit_m = cpu_request_m * 4  # 限制為請求的 4 倍
    
    # 記憶體基準 + 連接開銷（每個連接 ~1-2MB）
    base_memory_mi = 256
    total_conns = calculate_required_connections(
        RPSScenario(
            target_rps=total_rps,
            avg_latency_ms=avg_latency_ms,
            safety_factor=1.5,
            pod_replicas=pod_replicas
        )
    )
    connection_memory = total_conns / pod_replicas / 1000 * 500  # 粗略估算
    
    memory_request_mi = base_memory_mi + int(connection_memory)
    memory_limit_mi = memory_request_mi * 4
    
    return {
        "openfga": {
            "cpu_request": f"{cpu_request_m}m",
            "cpu_limit": f"{cpu_limit_m}m",
            "memory_request": f"{memory_request_mi}Mi",
            "memory_limit": f"{memory_limit_mi}Mi",
        },
        "mariadb": {
            "cpu_request": "1000m",
            "cpu_limit": "4000m",
            "memory_request": "2Gi",
            "memory_limit": "4Gi",
        }
    }


def print_recommendation(
    scenario: RPSScenario,
    galera_nodes: int = 3
) -> None:
    """
    打印完整的配置建議
    """
    # 計算需要的連接數
    total_conns = calculate_required_connections(scenario)
    
    # 計算每個 Pod 的配置
    max_open, max_idle = calculate_per_pod_config(
        total_conns,
        scenario.pod_replicas,
        galera_nodes
    )
    
    # 計算 Galera 配置
    galera_max_conns = calculate_galera_max_connections(
        scenario.target_rps * scenario.safety_factor / 1000 * scenario.avg_latency_ms,
        galera_nodes
    )
    
    # 計算資源
    resources = calculate_cpu_memory_resources(
        scenario.target_rps,
        scenario.avg_latency_ms,
        scenario.pod_replicas
    )
    
    print("\n" + "="*80)
    print("OpenFGA + MariaDB Galera 連接池配置建議")
    print("="*80)
    
    print(f"\n📊 場景參數:")
    print(f"  • 目標 RPS: {scenario.target_rps:,}")
    print(f"  • 平均延遲: {scenario.avg_latency_ms}ms")
    print(f"  • 安全係數: {scenario.safety_factor}")
    print(f"  • Pod 副本: {scenario.pod_replicas}")
    print(f"  • Galera 節點: {galera_nodes}")
    
    print(f"\n🔌 連接池配置:")
    print(f"  • 總需要連接數: {total_conns:,}")
    print(f"  • 每 Pod MaxOpenConns: {max_open}")
    print(f"  • 每 Pod MaxIdleConns: {max_idle}")
    print(f"  • 每個 Galera 節點平均連接: {total_conns // galera_nodes}")
    
    print(f"\n⏱️  超時設置:")
    timeout_config = recommend_idle_and_lifetime()
    for key, value in timeout_config.items():
        print(f"  • {key}: {value}")
    
    print(f"\n🗄️  MariaDB Galera 設置:")
    print(f"  • max_connections: {galera_max_conns}")
    print(f"  • wsrep_slave_threads: {galera_nodes * 2}")
    
    print(f"\n💾 資源配置 (每個 Pod):")
    for service, config in resources.items():
        print(f"\n  {service.upper()}:")
        for key, value in config.items():
            print(f"    • {key}: {value}")
    
    # 估算成本（AWS）
    print(f"\n💰 成本估算 (AWS m5 實例 - 美元/月):")
    openfga_cost = scenario.pod_replicas * 50  # m5.large ~$0.096/小時
    mariadb_cost = galera_nodes * 150  # m5.2xlarge ~$0.384/小時
    storage_cost = 30  # 每 100GB ~$10/月
    total_cost = openfga_cost + mariadb_cost + storage_cost
    
    print(f"  • OpenFGA ({scenario.pod_replicas} x m5.large): ${openfga_cost}")
    print(f"  • MariaDB ({galera_nodes} x m5.2xlarge): ${mariadb_cost}")
    print(f"  • 存儲 (300Gi EBS): ${storage_cost}")
    print(f"  • 總計: ${total_cost}/月")
    print(f"  • 每 1K RPS 成本: ${total_cost / (scenario.target_rps / 1000):.2f}")
    
    print("\n" + "="*80)


def generate_yaml_config(
    scenario: RPSScenario,
    galera_nodes: int = 3
) -> str:
    """
    生成 Kubernetes YAML 配置片段
    """
    total_conns = calculate_required_connections(scenario)
    max_open, max_idle = calculate_per_pod_config(
        total_conns,
        scenario.pod_replicas,
        galera_nodes
    )
    resources = calculate_cpu_memory_resources(
        scenario.target_rps,
        scenario.avg_latency_ms,
        scenario.pod_replicas
    )
    
    yaml = f"""
# OpenFGA Deployment 環境變數配置
env:
  - name: OPENFGA_DATASTORE_MAX_OPEN_CONNS
    value: "{max_open}"
  
  - name: OPENFGA_DATASTORE_MAX_IDLE_CONNS
    value: "{max_idle}"
  
  - name: OPENFGA_DATASTORE_CONN_MAX_IDLE_TIME
    value: "60s"
  
  - name: OPENFGA_DATASTORE_CONN_MAX_LIFETIME
    value: "10m"

# 資源配置
resources:
  requests:
    cpu: "{resources['openfga']['cpu_request']}"
    memory: "{resources['openfga']['memory_request']}"
  limits:
    cpu: "{resources['openfga']['cpu_limit']}"
    memory: "{resources['openfga']['memory_limit']}"

# Deployment replicas
replicas: {scenario.pod_replicas}
"""
    
    return yaml.strip()


# 預設場景
SCENARIOS = {
    "small": RPSScenario(
        target_rps=1000,
        avg_latency_ms=50,
        safety_factor=1.3,
        pod_replicas=3
    ),
    "medium": RPSScenario(
        target_rps=5000,
        avg_latency_ms=50,
        safety_factor=1.5,
        pod_replicas=5
    ),
    "large": RPSScenario(
        target_rps=10000,
        avg_latency_ms=50,
        safety_factor=1.5,
        pod_replicas=10
    ),
    "xlarge": RPSScenario(
        target_rps=20000,
        avg_latency_ms=50,
        safety_factor=1.5,
        pod_replicas=15
    ),
}


def main():
    """主函數"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║     OpenFGA + MariaDB Galera 連接池配置計算器                               ║
║     基於 500 萬筆資料和高 RPS 設計                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # 測試各種場景
    for name, scenario in SCENARIOS.items():
        print_recommendation(scenario)
        print("\n")
        
        # 打印 YAML 配置
        print(f"📝 {name.upper()} 場景 YAML 配置:")
        print("-" * 80)
        print(generate_yaml_config(scenario))
        print("-" * 80)
        print("\n")


if __name__ == "__main__":
    main()
    
    # 交互式模式
    print("\n💡 互動式配置計算:")
    print("-" * 80)
    
    try:
        target_rps = int(input("目標 RPS (默認 10000): ") or "10000")
        avg_latency = int(input("平均查詢延遲 ms (默認 50): ") or "50")
        pod_replicas = int(input("Pod 副本數 (默認 8): ") or "8")
        
        custom_scenario = RPSScenario(
            target_rps=target_rps,
            avg_latency_ms=avg_latency,
            safety_factor=1.5,
            pod_replicas=pod_replicas
        )
        
        print_recommendation(custom_scenario)
        
    except KeyboardInterrupt:
        print("\n\n已取消。")
    except ValueError:
        print("無效的輸入。")
