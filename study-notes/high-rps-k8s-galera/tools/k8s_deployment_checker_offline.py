#!/usr/bin/env python3
"""
OpenFGA + MariaDB Galera 配置檢查和驗證工具（離線模式）
支援沒有 kubectl 權限的情況下進行配置驗證
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class PodSpec:
    """Pod 規格"""
    name: str
    replicas: int
    cpu_request: str
    cpu_limit: str
    memory_request: str
    memory_limit: str
    type: str  # "openfga" or "mariadb"


class OfflineChecker:
    """離線配置檢查工具"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = {}
        self.recommendations = []
        
    def load_yaml_config(self, yaml_path: str) -> Dict:
        """載入 YAML 配置文件"""
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"❌ 無法載入 YAML: {e}")
            return {}
    
    def load_mock_config(self, json_path: str) -> bool:
        """載入模擬配置（JSON 格式）"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            return True
        except FileNotFoundError:
            print(f"⚠️  找不到配置文件: {json_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ 配置文件格式錯誤: {e}")
            return False
    
    def parse_deployment_yaml(self, yaml_path: str) -> List[PodSpec]:
        """解析 Deployment YAML 並提取資源配置"""
        yaml_data = self.load_yaml_config(yaml_path)
        pods = []
        
        if not yaml_data:
            return pods
        
        # 處理單個文件或多文件 YAML
        docs = yaml_data if isinstance(yaml_data, list) else [yaml_data]
        
        for doc in docs:
            if not doc or doc.get('kind') != 'Deployment':
                continue
            
            metadata = doc.get('metadata', {})
            spec = doc.get('spec', {})
            
            name = metadata.get('name', 'unknown')
            replicas = spec.get('replicas', 1)
            
            # 提取容器資源
            containers = spec.get('template', {}).get('spec', {}).get('containers', [])
            if not containers:
                continue
            
            container = containers[0]
            resources = container.get('resources', {})
            requests = resources.get('requests', {})
            limits = resources.get('limits', {})
            
            pod_type = "mariadb" if "mariadb" in name.lower() or "galera" in name.lower() else "openfga"
            
            pod = PodSpec(
                name=name,
                replicas=replicas,
                cpu_request=requests.get('cpu', 'N/A'),
                cpu_limit=limits.get('cpu', 'N/A'),
                memory_request=requests.get('memory', 'N/A'),
                memory_limit=limits.get('memory', 'N/A'),
                type=pod_type
            )
            pods.append(pod)
        
        return pods
    
    def check_openfga_config(self, pod: PodSpec) -> Dict:
        """檢查 OpenFGA 配置是否符合規範"""
        issues = []
        recommendations = []
        
        # CPU 檢查 (建議 500m-1000m)
        cpu_req = self._parse_cpu(pod.cpu_request)
        if cpu_req and cpu_req < 500:
            issues.append(f"CPU request {pod.cpu_request} 過低，建議至少 500m")
        elif cpu_req and cpu_req > 1000:
            recommendations.append(f"CPU request {pod.cpu_request} 較高，確認是否必要")
        
        # Memory 檢查 (建議 256Mi-512Mi)
        mem_req = self._parse_memory(pod.memory_request)
        if mem_req and mem_req < 256:
            issues.append(f"Memory request {pod.memory_request} 過低，建議至少 256Mi")
        elif mem_req and mem_req > 1024:
            recommendations.append(f"Memory request {pod.memory_request} 較高，可能過度配置")
        
        # 副本數檢查 (建議 8-12)
        if pod.replicas < 8:
            issues.append(f"副本數 {pod.replicas} 過低，建議至少 8 個以支持高 RPS")
        elif pod.replicas > 20:
            recommendations.append(f"副本數 {pod.replicas} 較高，確認是否符合成本預算")
        
        return {
            "pod": pod.name,
            "type": "openfga",
            "issues": issues,
            "recommendations": recommendations,
            "status": "warning" if issues else "ok"
        }
    
    def check_mariadb_config(self, pod: PodSpec) -> Dict:
        """檢查 MariaDB Galera 配置是否符合規範"""
        issues = []
        recommendations = []
        
        # CPU 檢查 (建議 1000m-2000m)
        cpu_req = self._parse_cpu(pod.cpu_request)
        if cpu_req and cpu_req < 1000:
            issues.append(f"CPU request {pod.cpu_request} 過低，建議至少 1000m (1 core)")
        
        # Memory 檢查 (建議 2Gi-4Gi)
        mem_req = self._parse_memory(pod.memory_request)
        if mem_req and mem_req < 2048:
            issues.append(f"Memory request {pod.memory_request} 過低，建議至少 2Gi")
        elif mem_req and mem_req > 8192:
            recommendations.append(f"Memory request {pod.memory_request} 較高，確認緩存需求")
        
        # 副本數檢查 (應該是 3)
        if pod.replicas != 3:
            issues.append(f"Galera 副本數應為 3，目前為 {pod.replicas}")
        
        return {
            "pod": pod.name,
            "type": "mariadb",
            "issues": issues,
            "recommendations": recommendations,
            "status": "warning" if issues else "ok"
        }
    
    def _parse_cpu(self, cpu_str: str) -> Optional[int]:
        """解析 CPU 字串為 millicores"""
        if cpu_str == 'N/A':
            return None
        
        try:
            if cpu_str.endswith('m'):
                return int(cpu_str[:-1])
            else:
                return int(float(cpu_str) * 1000)
        except (ValueError, AttributeError):
            return None
    
    def _parse_memory(self, mem_str: str) -> Optional[int]:
        """解析 Memory 字串為 MiB"""
        if mem_str == 'N/A':
            return None
        
        try:
            if mem_str.endswith('Mi'):
                return int(mem_str[:-2])
            elif mem_str.endswith('Gi'):
                return int(float(mem_str[:-2]) * 1024)
            elif mem_str.endswith('M'):
                return int(mem_str[:-1])
            elif mem_str.endswith('G'):
                return int(float(mem_str[:-1]) * 1024)
            else:
                return int(mem_str) // (1024 * 1024)
        except (ValueError, AttributeError):
            return None
    
    def check_connection_pool_config(self, yaml_path: str) -> Dict:
        """檢查連接池配置（從 ConfigMap 或環境變數）"""
        yaml_data = self.load_yaml_config(yaml_path)
        issues = []
        recommendations = []
        
        if not yaml_data:
            return {"status": "error", "message": "無法載入配置"}
        
        # 尋找 ConfigMap 或環境變數配置
        docs = yaml_data if isinstance(yaml_data, list) else [yaml_data]
        
        for doc in docs:
            if not doc:
                continue
            
            # 檢查 ConfigMap
            if doc.get('kind') == 'ConfigMap':
                data = doc.get('data', {})
                
                # 檢查連接池相關配置
                max_open_conns = data.get('OPENFGA_DATASTORE_MAX_OPEN_CONNS')
                max_idle_conns = data.get('OPENFGA_DATASTORE_MAX_IDLE_CONNS')
                
                if max_open_conns:
                    try:
                        max_open = int(max_open_conns)
                        if max_open < 100:
                            issues.append(f"MAX_OPEN_CONNS={max_open} 過低，建議至少 100")
                        elif max_open > 300:
                            recommendations.append(f"MAX_OPEN_CONNS={max_open} 較高，確認資料庫承受能力")
                    except ValueError:
                        pass
                
                if max_idle_conns:
                    try:
                        max_idle = int(max_idle_conns)
                        if max_idle < 50:
                            issues.append(f"MAX_IDLE_CONNS={max_idle} 過低，建議至少 50")
                    except ValueError:
                        pass
        
        return {
            "status": "ok" if not issues else "warning",
            "issues": issues,
            "recommendations": recommendations
        }
    
    def calculate_total_resources(self, pods: List[PodSpec]) -> Dict:
        """計算總資源需求"""
        total_cpu = 0
        total_memory = 0
        
        for pod in pods:
            cpu = self._parse_cpu(pod.cpu_request)
            mem = self._parse_memory(pod.memory_request)
            
            if cpu:
                total_cpu += cpu * pod.replicas
            if mem:
                total_memory += mem * pod.replicas
        
        return {
            "total_cpu_millicores": total_cpu,
            "total_cpu_cores": total_cpu / 1000,
            "total_memory_mi": total_memory,
            "total_memory_gi": total_memory / 1024
        }
    
    def print_yaml_analysis(self, yaml_path: str):
        """打印 YAML 分析報告"""
        print("\n" + "="*80)
        print("🔍 OpenFGA 部署配置分析（離線模式）")
        print("="*80)
        print(f"\n分析文件: {yaml_path}\n")
        
        # 解析 YAML
        pods = self.parse_deployment_yaml(yaml_path)
        
        if not pods:
            print("❌ 未找到有效的 Deployment 配置")
            return
        
        # 1. Pod 配置分析
        print("\n[1] Deployment 配置分析")
        print("-" * 80)
        
        openfga_pods = [p for p in pods if p.type == "openfga"]
        mariadb_pods = [p for p in pods if p.type == "mariadb"]
        
        print(f"\nOpenFGA Deployments: {len(openfga_pods)}")
        for pod in openfga_pods:
            print(f"\n  📦 {pod.name}")
            print(f"     副本數: {pod.replicas}")
            print(f"     CPU: request={pod.cpu_request}, limit={pod.cpu_limit}")
            print(f"     Memory: request={pod.memory_request}, limit={pod.memory_limit}")
            
            # 檢查配置
            check_result = self.check_openfga_config(pod)
            if check_result["issues"]:
                print(f"     ⚠️  問題:")
                for issue in check_result["issues"]:
                    print(f"        - {issue}")
            else:
                print(f"     ✅ 配置符合規範")
            
            if check_result["recommendations"]:
                print(f"     💡 建議:")
                for rec in check_result["recommendations"]:
                    print(f"        - {rec}")
        
        print(f"\n\nMariaDB Galera Deployments: {len(mariadb_pods)}")
        for pod in mariadb_pods:
            print(f"\n  🗄️  {pod.name}")
            print(f"     副本數: {pod.replicas}")
            print(f"     CPU: request={pod.cpu_request}, limit={pod.cpu_limit}")
            print(f"     Memory: request={pod.memory_request}, limit={pod.memory_limit}")
            
            # 檢查配置
            check_result = self.check_mariadb_config(pod)
            if check_result["issues"]:
                print(f"     ⚠️  問題:")
                for issue in check_result["issues"]:
                    print(f"        - {issue}")
            else:
                print(f"     ✅ 配置符合規範")
            
            if check_result["recommendations"]:
                print(f"     💡 建議:")
                for rec in check_result["recommendations"]:
                    print(f"        - {rec}")
        
        # 2. 資源總計
        print("\n\n[2] 資源需求總計")
        print("-" * 80)
        
        resources = self.calculate_total_resources(pods)
        print(f"\n  總 CPU: {resources['total_cpu_cores']:.2f} cores ({resources['total_cpu_millicores']} millicores)")
        print(f"  總 Memory: {resources['total_memory_gi']:.2f} GiB ({resources['total_memory_mi']} MiB)")
        
        # 檢查是否足夠
        if resources['total_cpu_cores'] < 10:
            print(f"\n  ⚠️  總 CPU 可能不足以支撐高 RPS（建議至少 10 cores）")
        else:
            print(f"\n  ✅ CPU 資源充足")
        
        if resources['total_memory_gi'] < 10:
            print(f"  ⚠️  總 Memory 可能不足（建議至少 10 GiB）")
        else:
            print(f"  ✅ Memory 資源充足")
        
        # 3. 連接池配置檢查
        print("\n\n[3] 連接池配置檢查")
        print("-" * 80)
        
        pool_check = self.check_connection_pool_config(yaml_path)
        if pool_check["status"] == "ok":
            print("  ✅ 連接池配置合理")
        elif pool_check["status"] == "warning":
            print("  ⚠️  連接池配置需要注意:")
            for issue in pool_check.get("issues", []):
                print(f"     - {issue}")
        
        if pool_check.get("recommendations"):
            print("  💡 建議:")
            for rec in pool_check["recommendations"]:
                print(f"     - {rec}")
        
        # 4. 高可用性檢查
        print("\n\n[4] 高可用性檢查")
        print("-" * 80)
        
        ha_checks = []
        
        # OpenFGA 副本數
        total_openfga_replicas = sum(p.replicas for p in openfga_pods)
        ha_checks.append(("OpenFGA 副本數 ≥ 8", total_openfga_replicas >= 8))
        
        # Galera 副本數
        total_galera_replicas = sum(p.replicas for p in mariadb_pods)
        ha_checks.append(("Galera 副本數 = 3", total_galera_replicas == 3))
        
        # 資源限制設置
        has_limits = all(p.cpu_limit != 'N/A' and p.memory_limit != 'N/A' for p in pods)
        ha_checks.append(("所有 Pod 設置資源限制", has_limits))
        
        for check_name, passed in ha_checks:
            status = "✅" if passed else "❌"
            print(f"  {status} {check_name}")
        
        # 總結
        print("\n" + "="*80)
        all_passed = all(passed for _, passed in ha_checks)
        
        if all_passed and total_openfga_replicas >= 8:
            print("✅ 配置符合高 RPS 設計規範！")
            print("\n建議的下一步:")
            print("  1. 使用 kubectl apply 部署配置")
            print("  2. 等待所有 Pod 就緒")
            print("  3. 執行線上檢查: python k8s_deployment_checker.py")
            print("  4. 進行性能測試")
        else:
            print("⚠️  配置尚有改進空間")
            print("\n建議的操作:")
            print("  1. 根據上述問題調整 YAML 配置")
            print("  2. 使用連接池計算器: python connection_pool_calculator.py")
            print("  3. 重新檢查配置")
        
        print("="*80 + "\n")
    
    def create_sample_mock_config(self, output_path: str):
        """創建範例模擬配置文件"""
        sample_config = {
            "namespace": "openfga-prod",
            "pods": [
                {
                    "name": "openfga-server-deployment-abc123",
                    "phase": "Running",
                    "type": "openfga",
                    "cpu": "800m",
                    "memory": "384Mi"
                },
                {
                    "name": "mariadb-galera-0",
                    "phase": "Running",
                    "type": "mariadb",
                    "cpu": "1200m",
                    "memory": "3072Mi"
                },
                {
                    "name": "mariadb-galera-1",
                    "phase": "Running",
                    "type": "mariadb",
                    "cpu": "1100m",
                    "memory": "2968Mi"
                },
                {
                    "name": "mariadb-galera-2",
                    "phase": "Running",
                    "type": "mariadb",
                    "cpu": "1150m",
                    "memory": "3024Mi"
                }
            ],
            "mysql_status": {
                "Threads_connected": 245,
                "Threads_running": 12,
                "Max_used_connections": 287
            },
            "galera_status": {
                "cluster_status": "Primary",
                "cluster_size": 3,
                "local_state": "Synced"
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 已創建範例配置: {output_path}")


def main():
    """主函數"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║     OpenFGA + MariaDB Galera 配置檢查工具（離線模式）                      ║
║     無需 kubectl 權限即可驗證配置                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    print("選擇模式:")
    print("  1. 分析 YAML 配置文件（推薦）")
    print("  2. 使用模擬數據檢查")
    print("  3. 生成範例模擬配置")
    
    choice = input("\n請選擇 (1/2/3): ").strip()
    
    checker = OfflineChecker()
    
    if choice == "1":
        yaml_path = input("\n請輸入 YAML 文件路徑: ").strip()
        if Path(yaml_path).exists():
            checker.print_yaml_analysis(yaml_path)
        else:
            print(f"❌ 找不到文件: {yaml_path}")
    
    elif choice == "2":
        json_path = input("\n請輸入模擬配置 JSON 路徑: ").strip()
        if checker.load_mock_config(json_path):
            print("✅ 已載入模擬配置")
            # 可以在這裡添加額外的分析邏輯
        else:
            print("❌ 無法載入配置")
    
    elif choice == "3":
        output_path = input("\n請輸入輸出路徑 (默認 mock_config.json): ").strip() or "mock_config.json"
        checker.create_sample_mock_config(output_path)
    
    else:
        print("❌ 無效選擇")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已中止檢查。")
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
