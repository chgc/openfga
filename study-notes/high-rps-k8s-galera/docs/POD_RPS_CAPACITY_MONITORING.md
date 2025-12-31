# 🔍 Pod RPS 容量監控指南

> **如何知道每一個 pod 能乘載的 rps 量有多少**

本指南提供完整的方法來監控和測量每個 OpenFGA Pod 的實際 RPS 容量。

---

## 📋 目錄

1. [快速開始](#快速開始)
2. [理論 vs 實際容量](#理論-vs-實際容量)
3. [實時監控 Pod RPS](#實時監控-pod-rps)
4. [容量測試方法](#容量測試方法)
5. [性能瓶頸識別](#性能瓶頸識別)
6. [自動化監控](#自動化監控)
7. [告警設置](#告警設置)

---

## 🚀 快速開始

### 30 秒查看當前 Pod RPS

```bash
# 使用 Prometheus 查詢（如果已部署）
kubectl port-forward -n monitoring svc/prometheus 9090:9090 &

# 打開瀏覽器訪問 http://localhost:9090 並執行以下查詢：
# 每個 Pod 的當前 RPS (1分鐘平均)
sum by(pod) (rate(grpc_server_handled_total{namespace="openfga-prod"}[1m]))
```

### 使用 kubectl 快速檢查

```bash
# 查看 Pod 列表和狀態
kubectl get pods -n openfga-prod -l app=openfga

# 查看特定 Pod 的日誌，觀察請求模式
kubectl logs -n openfga-prod <pod-name> --tail=100 | grep -i "check\|list"
```

---

## 💡 理論 vs 實際容量

### 理論容量計算

根據 `connection_pool_calculator.py` 的計算：

```python
# 理論 RPS 計算公式
理論 RPS/Pod = (MaxOpenConns × 1000) / (平均延遲ms × 安全係數)

# 例如：
MaxOpenConns = 150
平均延遲 = 50ms
安全係數 = 1.5

理論 RPS/Pod = (150 × 1000) / (50 × 1.5) = 2,000 RPS
```

### 實際容量因素

實際容量會受到以下因素影響：

| 因素 | 影響 | 典型範圍 |
|------|------|---------|
| **查詢複雜度** | 高複雜度降低 RPS | -30% ~ -50% |
| **數據庫延遲** | 網絡/磁碟延遲 | +10ms ~ +100ms |
| **CPU 限制** | CPU 節流降低性能 | -20% ~ -40% |
| **內存壓力** | GC 頻繁影響延遲 | -10% ~ -30% |
| **連接池飽和** | 連接等待時間 | -40% ~ -60% |

**實際容量 = 理論容量 × 影響因子 (通常 0.6 ~ 0.8)**

---

## 📊 實時監控 Pod RPS

### 方法 1: Prometheus Queries

OpenFGA 自動暴露 Prometheus 指標。以下是關鍵查詢：

#### 1.1 每個 Pod 的當前 RPS

```promql
# 1分鐘滾動平均 RPS (推薦)
sum by(pod) (
  rate(grpc_server_handled_total{
    namespace="openfga-prod",
    grpc_service="openfga.v1.OpenFGAService"
  }[1m])
)

# 5分鐘滾動平均 RPS (更平滑)
sum by(pod) (
  rate(grpc_server_handled_total{
    namespace="openfga-prod",
    grpc_service="openfga.v1.OpenFGAService"
  }[5m])
)
```

#### 1.2 按方法分類的 RPS

```promql
# 查看每個 Pod 處理的不同 API 方法的 RPS
sum by(pod, grpc_method) (
  rate(grpc_server_handled_total{
    namespace="openfga-prod",
    grpc_service="openfga.v1.OpenFGAService"
  }[1m])
)
```

#### 1.3 成功 vs 失敗請求

```promql
# 成功請求 (grpc_code="OK")
sum by(pod) (
  rate(grpc_server_handled_total{
    namespace="openfga-prod",
    grpc_code="OK"
  }[1m])
)

# 失敗請求
sum by(pod) (
  rate(grpc_server_handled_total{
    namespace="openfga-prod",
    grpc_code!="OK"
  }[1m])
)

# 錯誤率百分比
sum by(pod) (
  rate(grpc_server_handled_total{grpc_code!="OK"}[1m])
) 
/ 
sum by(pod) (
  rate(grpc_server_handled_total[1m])
) * 100
```

#### 1.4 Pod 容量使用率

```promql
# 當前 RPS vs 理論最大值（需要設置為 label）
(
  sum by(pod) (rate(grpc_server_handled_total[1m]))
  / 
  2000  # 替換為您的理論 RPS/Pod
) * 100
```

### 方法 2: 使用 kubectl + jq 實時監控

如果沒有 Prometheus，可以通過日誌分析：

```bash
# 創建實時 RPS 監控腳本
cat > /tmp/monitor_pod_rps.sh << 'EOF'
#!/bin/bash

NAMESPACE="openfga-prod"
POD_LABEL="app=openfga"
INTERVAL=10  # 秒

echo "監控 OpenFGA Pod RPS (每 ${INTERVAL} 秒更新)"
echo "================================================"

while true; do
  clear
  echo "時間: $(date)"
  echo "------------------------------------------------"
  
  for pod in $(kubectl get pods -n $NAMESPACE -l $POD_LABEL -o name | cut -d/ -f2); do
    # 計算過去 10 秒的請求數
    count=$(kubectl logs -n $NAMESPACE $pod --since=${INTERVAL}s 2>/dev/null | \
            grep -c "method=/openfga.v1.OpenFGAService/")
    
    rps=$(echo "scale=2; $count / $INTERVAL" | bc)
    
    echo "Pod: $pod"
    echo "  RPS: $rps"
    echo "  請求數 (${INTERVAL}s): $count"
    echo ""
  done
  
  sleep $INTERVAL
done
EOF

chmod +x /tmp/monitor_pod_rps.sh
/tmp/monitor_pod_rps.sh
```

### 方法 3: 使用 Grafana 儀表板

在 Grafana 中創建自定義面板：

```json
{
  "title": "Per-Pod RPS",
  "targets": [
    {
      "expr": "sum by(pod) (rate(grpc_server_handled_total{namespace=\"openfga-prod\"}[1m]))",
      "legendFormat": "{{pod}}"
    }
  ],
  "type": "graph"
}
```

---

## 🧪 容量測試方法

### 壓力測試確定實際容量

#### 測試 1: 單 Pod 最大 RPS 測試

```bash
# 1. 縮減到單個 Pod
kubectl scale deployment openfga -n openfga-prod --replicas=1

# 2. 等待 Pod 就緒
kubectl wait --for=condition=ready pod -l app=openfga -n openfga-prod --timeout=60s

# 3. 獲取 Pod IP
POD_IP=$(kubectl get pod -n openfga-prod -l app=openfga -o jsonpath='{.items[0].status.podIP}')

# 4. 使用 ghz 進行 gRPC 壓力測試
ghz --insecure \
  --proto ./proto/openfga/v1/openfga.proto \
  --call openfga.v1.OpenFGAService/Check \
  -d '{"store_id":"<your-store-id>","tuple_key":{"user":"user:test","relation":"viewer","object":"document:test"}}' \
  --connections 100 \
  --concurrency 100 \
  --total 100000 \
  --rps 500 \
  $POD_IP:8081

# 5. 逐步增加 RPS 直到延遲或錯誤率上升
# 測試不同 RPS: 500, 1000, 1500, 2000, 2500, 3000
for rps in 500 1000 1500 2000 2500 3000; do
  echo "測試 RPS: $rps"
  ghz --insecure \
    --proto ./proto/openfga/v1/openfga.proto \
    --call openfga.v1.OpenFGAService/Check \
    -d '{"store_id":"<store-id>","tuple_key":{"user":"user:test","relation":"viewer","object":"document:test"}}' \
    --connections 100 \
    --concurrency 100 \
    --total 10000 \
    --rps $rps \
    $POD_IP:8081 | tee /tmp/test_${rps}_rps.txt
  
  echo "完成 RPS $rps 測試，等待 30 秒..."
  sleep 30
done

# 6. 分析結果
echo "總結測試結果："
grep -h "Requests/sec\|Latency\|Error" /tmp/test_*_rps.txt
```

#### 測試 2: 持續負載測試

```bash
# 使用 k6 進行持續負載測試
cat > /tmp/load_test.js << 'EOF'
import grpc from 'k6/net/grpc';
import { check } from 'k6';

const client = new grpc.Client();
client.load(['./proto'], 'openfga/v1/openfga.proto');

export const options = {
  stages: [
    { duration: '2m', target: 100 },   // 升溫到 100 RPS
    { duration: '5m', target: 100 },   // 保持 100 RPS
    { duration: '2m', target: 500 },   // 升溫到 500 RPS
    { duration: '5m', target: 500 },   // 保持 500 RPS
    { duration: '2m', target: 1000 },  // 升溫到 1000 RPS
    { duration: '10m', target: 1000 }, // 保持 1000 RPS
    { duration: '2m', target: 0 },     // 降溫
  ],
};

export default () => {
  client.connect('openfga.openfga-prod.svc.cluster.local:8081', { plaintext: true });
  
  const response = client.invoke('openfga.v1.OpenFGAService/Check', {
    store_id: '<your-store-id>',
    tuple_key: {
      user: 'user:test',
      relation: 'viewer',
      object: 'document:test'
    }
  });
  
  check(response, {
    'status is OK': (r) => r && r.status === grpc.StatusOK,
  });
  
  client.close();
};
EOF

# 運行負載測試
k6 run /tmp/load_test.js
```

### 容量測試結果分析

記錄以下指標來確定容量：

| 指標 | 健康範圍 | 警告閾值 | 危險閾值 |
|------|---------|---------|---------|
| **p50 延遲** | < 50ms | 50-100ms | > 100ms |
| **p99 延遲** | < 150ms | 150-300ms | > 300ms |
| **錯誤率** | < 0.1% | 0.1-1% | > 1% |
| **CPU 使用率** | < 60% | 60-80% | > 80% |
| **內存使用率** | < 70% | 70-85% | > 85% |

**Pod 最大容量 = 最後一個符合"健康範圍"的 RPS 值**

---

## 🔍 性能瓶頸識別

### 檢查清單：識別限制因素

#### 1. CPU 瓶頸檢測

```bash
# 查看 Pod CPU 使用率
kubectl top pods -n openfga-prod -l app=openfga

# 詳細的 CPU 節流檢查
kubectl exec -n openfga-prod <pod-name> -- cat /sys/fs/cgroup/cpu/cpu.stat

# 如果 CPU 使用率 > 80%，這可能是瓶頸
# 解決方案：增加 CPU limits 或增加副本數
```

#### 2. 內存瓶頸檢測

```bash
# 查看內存使用
kubectl top pods -n openfga-prod -l app=openfga

# 查看 OOM 事件
kubectl get events -n openfga-prod | grep -i "oom\|memory"

# 解決方案：增加 memory limits 或優化連接池
```

#### 3. 數據庫連接池瓶頸

```bash
# 檢查連接數是否達到上限
kubectl exec -n openfga-prod mariadb-galera-0 -- mysql -e "
  SHOW STATUS LIKE 'Threads_connected';
  SHOW VARIABLES LIKE 'max_connections';
"

# 查看 OpenFGA 連接池指標 (Prometheus)
# 等待連接的請求數
rate(openfga_datastore_connection_wait_duration_count[1m])

# 如果等待時間增加，需要調整 MaxOpenConns
```

#### 4. 數據庫查詢延遲

```bash
# 檢查慢查詢
kubectl exec -n openfga-prod mariadb-galera-0 -- mysql -e "
  SELECT * FROM mysql.slow_log ORDER BY query_time DESC LIMIT 10;
"

# Prometheus 查詢數據庫延遲
histogram_quantile(0.99, 
  rate(openfga_datastore_query_duration_ms_bucket[5m])
)
```

### 瓶頸決策樹

```
RPS 無法提升？
│
├─ CPU 使用率 > 80%？
│  ├─ 是 → 增加 CPU limits 或增加副本
│  └─ 否 → 繼續
│
├─ 內存使用率 > 85%？
│  ├─ 是 → 增加 memory limits 或減少連接數
│  └─ 否 → 繼續
│
├─ 連接池等待時間 > 10ms？
│  ├─ 是 → 增加 MaxOpenConns
│  └─ 否 → 繼續
│
├─ 數據庫延遲 > 100ms？
│  ├─ 是 → 優化查詢、添加索引、或擴展數據庫
│  └─ 否 → 繼續
│
└─ 檢查網絡延遲和磁盤 I/O
```

---

## 🤖 自動化監控

### Python 腳本：Pod RPS 容量監控器

```python
#!/usr/bin/env python3
"""
pod_rps_monitor.py - 自動監控每個 Pod 的 RPS 和容量使用率
"""

import subprocess
import json
import time
from datetime import datetime
from typing import Dict, List

class PodRPSMonitor:
    def __init__(self, namespace: str = "openfga-prod", 
                 theoretical_rps_per_pod: int = 2000):
        self.namespace = namespace
        self.theoretical_rps = theoretical_rps_per_pod
        self.prometheus_url = "http://localhost:9090"
    
    def get_pod_rps(self) -> Dict[str, float]:
        """
        從 Prometheus 獲取每個 Pod 的當前 RPS
        """
        query = f'''
        sum by(pod) (
          rate(grpc_server_handled_total{{
            namespace="{self.namespace}",
            grpc_service="openfga.v1.OpenFGAService"
          }}[1m])
        )
        '''
        
        # 使用 kubectl port-forward 或直接 Prometheus API
        cmd = [
            "curl", "-s", "-G",
            f"{self.prometheus_url}/api/v1/query",
            "--data-urlencode", f"query={query}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error querying Prometheus: {result.stderr}")
            return {}
        
        data = json.loads(result.stdout)
        
        pod_rps = {}
        if data.get("status") == "success":
            for item in data["data"]["result"]:
                pod_name = item["metric"]["pod"]
                rps = float(item["value"][1])
                pod_rps[pod_name] = rps
        
        return pod_rps
    
    def get_pod_resources(self) -> Dict[str, Dict[str, float]]:
        """
        獲取 Pod 資源使用率
        """
        cmd = [
            "kubectl", "top", "pods",
            "-n", self.namespace,
            "-l", "app=openfga",
            "--no-headers"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        pod_resources = {}
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split()
            pod_name = parts[0]
            cpu = parts[1].replace('m', '')
            memory = parts[2].replace('Mi', '')
            
            pod_resources[pod_name] = {
                'cpu_millicores': float(cpu),
                'memory_mi': float(memory)
            }
        
        return pod_resources
    
    def calculate_capacity_usage(self, current_rps: float) -> float:
        """
        計算容量使用百分比
        """
        return (current_rps / self.theoretical_rps) * 100
    
    def print_report(self, pod_rps: Dict[str, float], 
                     pod_resources: Dict[str, Dict[str, float]]):
        """
        打印監控報告
        """
        print("\n" + "="*80)
        print(f"OpenFGA Pod RPS 容量監控報告")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"理論容量: {self.theoretical_rps} RPS/Pod")
        print("="*80)
        
        total_rps = 0
        for pod_name in sorted(pod_rps.keys()):
            rps = pod_rps[pod_name]
            total_rps += rps
            capacity_pct = self.calculate_capacity_usage(rps)
            
            resources = pod_resources.get(pod_name, {})
            cpu = resources.get('cpu_millicores', 0)
            memory = resources.get('memory_mi', 0)
            
            # 狀態指示器
            status = "🟢"
            if capacity_pct > 80:
                status = "🔴"
            elif capacity_pct > 60:
                status = "🟡"
            
            print(f"\n{status} Pod: {pod_name}")
            print(f"   當前 RPS: {rps:.2f}")
            print(f"   容量使用: {capacity_pct:.1f}%")
            print(f"   CPU: {cpu:.0f}m")
            print(f"   Memory: {memory:.0f}Mi")
            
            if capacity_pct > 80:
                print(f"   ⚠️  警告: Pod 接近容量上限!")
        
        print("\n" + "-"*80)
        print(f"總計 RPS: {total_rps:.2f}")
        print(f"平均 RPS/Pod: {total_rps/len(pod_rps):.2f}")
        print(f"集群總容量: {self.theoretical_rps * len(pod_rps)} RPS")
        print(f"集群容量使用: {(total_rps/(self.theoretical_rps * len(pod_rps)))*100:.1f}%")
        print("="*80 + "\n")
    
    def run(self, interval: int = 10):
        """
        持續監控
        """
        print("啟動 Pod RPS 監控器...")
        print("按 Ctrl+C 停止\n")
        
        try:
            while True:
                pod_rps = self.get_pod_rps()
                pod_resources = self.get_pod_resources()
                
                if pod_rps:
                    self.print_report(pod_rps, pod_resources)
                else:
                    print("無法獲取 RPS 數據，檢查 Prometheus 連接...")
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            print("\n監控已停止")

if __name__ == "__main__":
    # 確保 Prometheus port-forward 正在運行:
    # kubectl port-forward -n monitoring svc/prometheus 9090:9090
    
    monitor = PodRPSMonitor(
        namespace="openfga-prod",
        theoretical_rps_per_pod=2000  # 根據您的配置調整
    )
    
    monitor.run(interval=10)
```

### 使用監控腳本

```bash
# 1. 確保 Prometheus port-forward 正在運行
kubectl port-forward -n monitoring svc/prometheus 9090:9090 &

# 2. 創建並運行監控腳本
python3 study-notes/high-rps-k8s-galera/tools/pod_rps_monitor.py

# 3. 查看實時報告
```

---

## 🚨 告警設置

### Prometheus 告警規則

創建 `pod-rps-alerts.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: openfga-rps-alerts
  namespace: monitoring
data:
  pod-rps-alerts.yml: |
    groups:
    - name: openfga_pod_rps
      interval: 30s
      rules:
      
      # 單個 Pod RPS 過高
      - alert: PodRPSHigh
        expr: |
          sum by(pod) (
            rate(grpc_server_handled_total{
              namespace="openfga-prod",
              grpc_service="openfga.v1.OpenFGAService"
            }[1m])
          ) > 1600
        for: 2m
        labels:
          severity: warning
          component: openfga
        annotations:
          summary: "Pod {{ $labels.pod }} RPS 過高"
          description: "Pod {{ $labels.pod }} 當前 RPS 為 {{ $value | humanize }}，超過 80% 容量 (2000 RPS)"
      
      # 單個 Pod RPS 臨界
      - alert: PodRPSCritical
        expr: |
          sum by(pod) (
            rate(grpc_server_handled_total{
              namespace="openfga-prod",
              grpc_service="openfga.v1.OpenFGAService"
            }[1m])
          ) > 1900
        for: 1m
        labels:
          severity: critical
          component: openfga
        annotations:
          summary: "Pod {{ $labels.pod }} RPS 臨界"
          description: "Pod {{ $labels.pod }} 當前 RPS 為 {{ $value | humanize }}，超過 95% 容量，需要立即擴容!"
      
      # 集群總 RPS 過高
      - alert: ClusterRPSHigh
        expr: |
          sum(
            rate(grpc_server_handled_total{
              namespace="openfga-prod",
              grpc_service="openfga.v1.OpenFGAService"
            }[1m])
          ) > 16000
        for: 2m
        labels:
          severity: warning
          component: openfga
        annotations:
          summary: "OpenFGA 集群 RPS 過高"
          description: "集群總 RPS 為 {{ $value | humanize }}，超過預期容量 80%"
      
      # Pod 間負載不均衡
      - alert: PodRPSImbalance
        expr: |
          (
            max by(namespace) (
              sum by(pod) (
                rate(grpc_server_handled_total{
                  namespace="openfga-prod"
                }[5m])
              )
            )
            /
            avg by(namespace) (
              sum by(pod) (
                rate(grpc_server_handled_total{
                  namespace="openfga-prod"
                }[5m])
              )
            )
          ) > 2
        for: 5m
        labels:
          severity: info
          component: openfga
        annotations:
          summary: "OpenFGA Pod 負載不均衡"
          description: "最高 RPS Pod 是平均值的 {{ $value | humanize }} 倍，檢查負載均衡器配置"
      
      # 錯誤率過高
      - alert: PodErrorRateHigh
        expr: |
          (
            sum by(pod) (
              rate(grpc_server_handled_total{
                namespace="openfga-prod",
                grpc_code!="OK"
              }[1m])
            )
            /
            sum by(pod) (
              rate(grpc_server_handled_total{
                namespace="openfga-prod"
              }[1m])
            )
          ) * 100 > 1
        for: 2m
        labels:
          severity: warning
          component: openfga
        annotations:
          summary: "Pod {{ $labels.pod }} 錯誤率過高"
          description: "Pod {{ $labels.pod }} 錯誤率為 {{ $value | humanize }}%，超過 1% 閾值"
```

### 應用告警規則

```bash
# 應用告警配置
kubectl apply -f pod-rps-alerts.yaml

# 重載 Prometheus 配置
kubectl exec -n monitoring prometheus-0 -- killall -HUP prometheus
```

---

## 📈 最佳實踐總結

### 1. 定期容量測試

```bash
# 每月執行一次容量基準測試
# 記錄結果以追蹤性能趨勢
```

### 2. 設置合理的容量目標

| 環境 | 目標容量使用率 | 理由 |
|------|--------------|------|
| **開發** | < 30% | 允許大量測試活動 |
| **預生產** | 40-60% | 接近生產但有緩衝 |
| **生產** | 50-70% | 平衡成本和性能 |
| **峰值時段** | < 80% | 保留應對突發流量的空間 |

### 3. 自動擴縮容配置

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: openfga-hpa
  namespace: openfga-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: openfga
  minReplicas: 3
  maxReplicas: 20
  metrics:
  # 基於 CPU
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  
  # 基於內存
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 75
  
  # 基於自定義指標 (RPS)
  - type: Pods
    pods:
      metric:
        name: grpc_server_handled_total
      target:
        type: AverageValue
        averageValue: "1500"  # 每個 Pod 1500 RPS 時擴容
  
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # 5分鐘穩定期
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60  # 1分鐘穩定期
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
```

### 4. 監控儀表板檢查清單

建立 Grafana 儀表板，包含：

- [ ] 每個 Pod 的實時 RPS 時間序列圖
- [ ] 容量使用率儀表（當前 RPS / 理論最大值）
- [ ] Pod 間 RPS 分佈（直方圖）
- [ ] 錯誤率趨勢
- [ ] 延遲分佈（p50, p90, p99）
- [ ] 資源使用率（CPU, Memory）
- [ ] 連接池使用情況

---

## 🎯 快速決策指南

### 何時需要擴容？

```
如果以下任一條件滿足，考慮擴容：

✅ 任何 Pod 的平均 RPS > 理論容量的 70%（持續 5 分鐘）
✅ p99 延遲 > 200ms（持續 2 分鐘）
✅ 錯誤率 > 0.5%（持續 1 分鐘）
✅ CPU 使用率 > 75%（持續 5 分鐘）
✅ 連接池等待時間 > 10ms
```

### 如何驗證容量調整？

```bash
# 1. 調整配置（例如：增加副本數）
kubectl scale deployment openfga -n openfga-prod --replicas=12

# 2. 等待 Pod 就緒
kubectl wait --for=condition=ready pod -l app=openfga -n openfga-prod --timeout=120s

# 3. 監控 5-10 分鐘
python3 tools/pod_rps_monitor.py

# 4. 驗證指標改善
#    - 每個 Pod RPS 降低
#    - 延遲下降
#    - 錯誤率下降
#    - CPU/內存使用率正常
```

---

## 📚 相關文檔

- [connection_pool_calculator.py](../tools/connection_pool_calculator.py) - 理論容量計算
- [MONITORING_AND_TROUBLESHOOTING.md](./MONITORING_AND_TROUBLESHOOTING.md) - 故障排除
- [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) - 快速命令參考

---

## 🙋 常見問題

### Q: 理論容量和實際容量差距很大怎麼辦？

**A**: 這是正常的。實際容量受多種因素影響：

1. 使用容量測試確定實際容量
2. 調整 `theoretical_rps_per_pod` 參數為實測值
3. 檢查性能瓶頸並逐一優化

### Q: 如何在沒有 Prometheus 的情況下監控？

**A**: 使用本文檔中的 kubectl + 日誌分析腳本，或者：

```bash
# 簡單的日誌計數方法
kubectl logs -n openfga-prod deployment/openfga --since=60s | \
  grep -c "method=/openfga.v1.OpenFGAService/" | \
  awk '{print $1/60 " RPS"}'
```

### Q: 多少 RPS 算是"高負載"？

**A**: 這取決於：
- **查詢複雜度**: 簡單查詢可能支持 3000+ RPS/Pod，複雜查詢可能只有 500 RPS/Pod
- **數據規模**: 500萬筆資料 vs 5000萬筆資料的性能不同
- **資源配置**: CPU/內存限制直接影響容量

建議通過實際負載測試確定您環境的"高負載"閾值。

---

**最後更新**: 2025-12-31  
**版本**: 1.0  
**狀態**: ✅ 生產就緒
