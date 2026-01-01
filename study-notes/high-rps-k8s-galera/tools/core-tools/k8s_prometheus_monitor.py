#!/usr/bin/env python3
"""
OpenFGA + MariaDB Galera Prometheus 監控工具
使用 Prometheus metrics 替代 kubectl 進行實時監控
"""

import requests
import json
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class MetricPoint:
    """指標數據點"""
    timestamp: datetime
    value: float
    labels: Dict[str, str]


class PrometheusMonitor:
    """Prometheus 監控工具"""
    
    def __init__(self, prometheus_url: str = "http://localhost:9090", namespace: str = "openfga-prod"):
        """
        初始化 Prometheus 監控器
        
        Args:
            prometheus_url: Prometheus 服務地址（默認 localhost:9090）
            namespace: Kubernetes namespace
        """
        self.prometheus_url = prometheus_url
        self.namespace = namespace
        self.session = requests.Session()
        self.session.timeout = 10
    
    def query(self, query_expr: str, instant: bool = True) -> Dict:
        """
        執行 Prometheus 查詢
        
        Args:
            query_expr: PromQL 表達式
            instant: 是否查詢瞬時值（True）還是範圍值（False）
        
        Returns:
            查詢結果
        """
        try:
            endpoint = "query" if instant else "query_range"
            url = f"{self.prometheus_url}/api/v1/{endpoint}"
            
            params = {"query": query_expr}
            
            if not instant:
                params["start"] = (datetime.now() - timedelta(hours=1)).isoformat()
                params["end"] = datetime.now().isoformat()
                params["step"] = "30s"
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def check_prometheus_health(self) -> bool:
        """檢查 Prometheus 是否可用"""
        try:
            response = self.session.get(f"{self.prometheus_url}/-/healthy", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_pod_status(self) -> Dict:
        """
        使用 Prometheus 獲取 Pod 狀態
        查詢: kube_pod_status_phase
        """
        query = f'kube_pod_status_phase{{namespace="{self.namespace}"}}'
        result = self.query(query)
        
        if result.get("status") != "success":
            return {"status": "error", "message": "Failed to query pod status"}
        
        pods = {}
        running_count = 0
        
        for metric in result.get("data", {}).get("result", []):
            labels = metric.get("labels", {})
            pod_name = labels.get("pod", "unknown")
            phase = labels.get("phase", "unknown")
            value = int(metric.get("value", [0, 0])[1])
            
            if value == 1:  # 指標值為 1 表示該狀態為真
                pods[pod_name] = phase
                if phase == "Running":
                    running_count += 1
        
        return {
            "status": "success",
            "total": len(pods),
            "ready": running_count,
            "pods": pods
        }
    
    def get_cpu_usage(self, pod_filter: str = "") -> Dict:
        """
        獲取 CPU 使用情況（百分比）
        查詢: rate(container_cpu_usage_seconds_total[5m]) * 100
        """
        namespace_filter = f'namespace="{self.namespace}"'
        if pod_filter:
            query = f'rate(container_cpu_usage_seconds_total{{{namespace_filter},pod=~"{pod_filter}"}}[5m]) * 100'
        else:
            query = f'rate(container_cpu_usage_seconds_total{{{namespace_filter}}}[5m]) * 100'
        
        result = self.query(query)
        
        if result.get("status") != "success":
            return {"status": "error", "message": "Failed to query CPU usage"}
        
        cpu_data = {}
        for metric in result.get("data", {}).get("result", []):
            labels = metric.get("labels", {})
            pod_name = labels.get("pod", labels.get("pod_name", "unknown"))
            value = float(metric.get("value", [0, 0])[1])
            
            if pod_name not in cpu_data:
                cpu_data[pod_name] = []
            cpu_data[pod_name].append(value)
        
        # 計算平均值
        cpu_average = {pod: sum(vals) / len(vals) for pod, vals in cpu_data.items()}
        
        return {
            "status": "success",
            "cpu_percent": cpu_average,
            "total_avg": sum(cpu_average.values()) / len(cpu_average) if cpu_average else 0
        }
    
    def get_memory_usage(self, pod_filter: str = "") -> Dict:
        """
        獲取 Memory 使用情況（MiB）
        查詢: container_memory_working_set_bytes / 1024 / 1024
        """
        namespace_filter = f'namespace="{self.namespace}"'
        if pod_filter:
            query = f'container_memory_working_set_bytes{{{namespace_filter},pod=~"{pod_filter}"}} / 1024 / 1024'
        else:
            query = f'container_memory_working_set_bytes{{{namespace_filter}}} / 1024 / 1024'
        
        result = self.query(query)
        
        if result.get("status") != "success":
            return {"status": "error", "message": "Failed to query memory usage"}
        
        mem_data = {}
        for metric in result.get("data", {}).get("result", []):
            labels = metric.get("labels", {})
            pod_name = labels.get("pod", labels.get("pod_name", "unknown"))
            value = float(metric.get("value", [0, 0])[1])
            
            mem_data[pod_name] = value
        
        total_memory = sum(mem_data.values())
        
        return {
            "status": "success",
            "memory_mib": mem_data,
            "total_mib": total_memory,
            "total_gib": total_memory / 1024
        }
    
    def get_network_io(self, pod_filter: str = "") -> Dict:
        """
        獲取網絡 I/O 情況（字節/秒）
        查詢: rate(container_network_*_bytes_total[5m])
        """
        namespace_filter = f'namespace="{self.namespace}"'
        
        # 進流量
        recv_query = f'rate(container_network_receive_bytes_total{{{namespace_filter}}}[5m])'
        # 出流量
        trans_query = f'rate(container_network_transmit_bytes_total{{{namespace_filter}}}[5m])'
        
        recv_result = self.query(recv_query)
        trans_result = self.query(trans_query)
        
        network_data = {}
        
        for metric in recv_result.get("data", {}).get("result", []):
            labels = metric.get("labels", {})
            pod_name = labels.get("pod", "unknown")
            value = float(metric.get("value", [0, 0])[1])
            
            if pod_name not in network_data:
                network_data[pod_name] = {}
            network_data[pod_name]["receive_bytes_per_sec"] = value
        
        for metric in trans_result.get("data", {}).get("result", []):
            labels = metric.get("labels", {})
            pod_name = labels.get("pod", "unknown")
            value = float(metric.get("value", [0, 0])[1])
            
            if pod_name not in network_data:
                network_data[pod_name] = {}
            network_data[pod_name]["transmit_bytes_per_sec"] = value
        
        return {
            "status": "success",
            "network_io": network_data
        }
    
    def get_mysql_metrics(self) -> Dict:
        """獲取 MySQL/Galera 相關指標"""
        metrics = {
            "connections": self._get_metric('mysql_global_status_threads_connected'),
            "questions": self._get_metric('mysql_global_status_questions'),
            "slow_queries": self._get_metric('mysql_global_status_slow_queries'),
            "innodb_reads": self._get_metric('mysql_global_status_innodb_rows_read'),
            "innodb_writes": self._get_metric('mysql_global_status_innodb_rows_written'),
            "innodb_deletes": self._get_metric('mysql_global_status_innodb_rows_deleted'),
        }
        
        return {
            "status": "success",
            "metrics": metrics
        }
    
    def _get_metric(self, metric_name: str) -> Dict:
        """獲取特定指標"""
        query = f'{metric_name}{{namespace="{self.namespace}"}}'
        result = self.query(query)
        
        if result.get("status") != "success":
            return {}
        
        data = {}
        for metric in result.get("data", {}).get("result", []):
            labels = metric.get("labels", {})
            pod_name = labels.get("pod", labels.get("instance", "unknown"))
            value = float(metric.get("value", [0, 0])[1])
            data[pod_name] = value
        
        return data
    
    def get_galera_cluster_status(self) -> Dict:
        """獲取 Galera 集群狀態"""
        metrics = {
            "cluster_size": self._get_metric('mysql_global_status_wsrep_cluster_size'),
            "cluster_status": self._get_metric('mysql_global_status_wsrep_cluster_status'),
            "ready": self._get_metric('mysql_global_status_wsrep_ready'),
        }
        
        return {
            "status": "success",
            "galera": metrics
        }
    
    def get_openfga_request_metrics(self) -> Dict:
        """獲取 OpenFGA API 請求指標"""
        metrics = {
            "requests_total": self._get_metric('openfga_http_requests_total'),
            "request_duration": self._get_metric('openfga_http_request_duration_seconds_bucket'),
            "errors": self._get_metric('openfga_http_requests_total{status=~"5.."}'),
        }
        
        return {
            "status": "success",
            "api_metrics": metrics
        }
    
    def print_dashboard(self, interval: int = 5, continuous: bool = False):
        """
        打印監控儀表板
        
        Args:
            interval: 刷新間隔（秒）
            continuous: 是否持續監控
        """
        print("\n" + "="*100)
        print("🔍 OpenFGA + MariaDB Galera Prometheus 實時監控")
        print("="*100)
        
        if not self.check_prometheus_health():
            print(f"❌ 無法連接到 Prometheus ({self.prometheus_url})")
            print("   請確保 Prometheus 已啟動並可訪問")
            return
        
        print(f"✅ 已連接到 Prometheus")
        print(f"   Namespace: {self.namespace}")
        print(f"   刷新間隔: {interval}秒")
        print("="*100)
        
        try:
            iteration = 0
            while True:
                iteration += 1
                print(f"\n[監控週期 #{iteration}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("-" * 100)
                
                # 1. Pod 狀態
                print("\n[1] Pod 狀態")
                pod_status = self.get_pod_status()
                if pod_status["status"] == "success":
                    print(f"✅ 總計: {pod_status['total']} Pod")
                    print(f"   就緒: {pod_status['ready']} Running, {pod_status['total'] - pod_status['ready']} 其他狀態")
                    
                    # 分類顯示
                    openfga_count = sum(1 for p in pod_status['pods'] if 'openfga' in p and pod_status['pods'][p] == "Running")
                    galera_count = sum(1 for p in pod_status['pods'] if 'mariadb' in p and pod_status['pods'][p] == "Running")
                    
                    print(f"   OpenFGA: {openfga_count} Running")
                    print(f"   MariaDB: {galera_count} Running")
                else:
                    print(f"❌ {pod_status.get('message')}")
                
                # 2. CPU 使用
                print("\n[2] CPU 使用率")
                cpu_data = self.get_cpu_usage()
                if cpu_data["status"] == "success":
                    print(f"✅ 平均 CPU: {cpu_data['total_avg']:.2f}%")
                    openfga_cpu = {k: v for k, v in cpu_data['cpu_percent'].items() if 'openfga' in k}
                    galera_cpu = {k: v for k, v in cpu_data['cpu_percent'].items() if 'mariadb' in k}
                    
                    if openfga_cpu:
                        avg_openfga = sum(openfga_cpu.values()) / len(openfga_cpu)
                        print(f"   OpenFGA 平均: {avg_openfga:.2f}%")
                    
                    if galera_cpu:
                        avg_galera = sum(galera_cpu.values()) / len(galera_cpu)
                        print(f"   MariaDB 平均: {avg_galera:.2f}%")
                else:
                    print(f"⚠️  {cpu_data.get('message')}")
                
                # 3. Memory 使用
                print("\n[3] 內存使用")
                mem_data = self.get_memory_usage()
                if mem_data["status"] == "success":
                    print(f"✅ 總計: {mem_data['total_gib']:.2f} GiB ({mem_data['total_mib']:.0f} MiB)")
                    
                    openfga_mem = {k: v for k, v in mem_data['memory_mib'].items() if 'openfga' in k}
                    galera_mem = {k: v for k, v in mem_data['memory_mib'].items() if 'mariadb' in k}
                    
                    if openfga_mem:
                        total_openfga = sum(openfga_mem.values())
                        print(f"   OpenFGA: {total_openfga/1024:.2f} GiB")
                    
                    if galera_mem:
                        total_galera = sum(galera_mem.values())
                        print(f"   MariaDB: {total_galera/1024:.2f} GiB")
                else:
                    print(f"⚠️  {mem_data.get('message')}")
                
                # 4. 網絡 I/O
                print("\n[4] 網絡 I/O (字節/秒)")
                network_data = self.get_network_io()
                if network_data["status"] == "success":
                    total_recv = sum(data.get('receive_bytes_per_sec', 0) for data in network_data['network_io'].values())
                    total_trans = sum(data.get('transmit_bytes_per_sec', 0) for data in network_data['network_io'].values())
                    
                    print(f"✅ 進流量: {total_recv/1024:.2f} KB/s")
                    print(f"   出流量: {total_trans/1024:.2f} KB/s")
                else:
                    print(f"⚠️  {network_data.get('message')}")
                
                # 5. MySQL 指標
                print("\n[5] MySQL 連接和查詢")
                mysql_data = self.get_mysql_metrics()
                if mysql_data["status"] == "success":
                    connections = mysql_data['metrics'].get('connections', {})
                    if connections:
                        total_conn = sum(connections.values())
                        print(f"✅ 活動連接: {total_conn:.0f}")
                    
                    questions = mysql_data['metrics'].get('questions', {})
                    if questions:
                        total_q = sum(questions.values())
                        print(f"   總查詢: {total_q:.0f}")
                else:
                    print(f"⚠️  {mysql_data.get('message')}")
                
                # 6. Galera 狀態
                print("\n[6] Galera 集群狀態")
                galera_status = self.get_galera_cluster_status()
                if galera_status["status"] == "success":
                    cluster_size = galera_status['galera'].get('cluster_size', {})
                    if cluster_size:
                        size = list(cluster_size.values())[0] if cluster_size else 0
                        print(f"✅ 集群大小: {size:.0f}")
                    
                    ready = galera_status['galera'].get('ready', {})
                    if ready:
                        is_ready = list(ready.values())[0] if ready else 0
                        status_icon = "✅" if is_ready == 1 else "❌"
                        print(f"   {status_icon} 就緒: {'是' if is_ready == 1 else '否'}")
                else:
                    print(f"⚠️  {galera_status.get('message')}")
                
                print("-" * 100)
                
                if not continuous:
                    break
                
                print(f"\n⏳ {interval}秒後更新...\n")
                time.sleep(interval)
        
        except KeyboardInterrupt:
            print("\n\n✋ 已停止監控\n")
    
    def print_summary_report(self):
        """打印摘要報告"""
        print("\n" + "="*100)
        print("📊 OpenFGA + MariaDB Galera 監控摘要")
        print("="*100)
        
        if not self.check_prometheus_health():
            print(f"❌ 無法連接到 Prometheus")
            return
        
        # Pod 狀態
        pod_status = self.get_pod_status()
        print("\n[Pod 狀態]")
        if pod_status["status"] == "success":
            print(f"✅ 總計: {pod_status['total']}")
            print(f"   就緒: {pod_status['ready']}/{pod_status['total']}")
            
            if pod_status['ready'] == pod_status['total']:
                print("   ✅ 所有 Pod 就緒")
            else:
                print(f"   ⚠️  {pod_status['total'] - pod_status['ready']} Pod 未就緒")
        
        # 資源使用
        cpu_data = self.get_cpu_usage()
        mem_data = self.get_memory_usage()
        
        print("\n[資源使用]")
        if cpu_data["status"] == "success":
            print(f"✅ CPU: {cpu_data['total_avg']:.2f}%")
        
        if mem_data["status"] == "success":
            print(f"✅ Memory: {mem_data['total_gib']:.2f} GiB")
        
        # 健康檢查
        print("\n[健康狀態]")
        
        checks = []
        if pod_status["status"] == "success":
            checks.append(("所有 Pod 就緒", pod_status['ready'] == pod_status['total']))
        
        if cpu_data["status"] == "success":
            checks.append(("CPU 使用 < 80%", cpu_data['total_avg'] < 80))
        
        if mem_data["status"] == "success":
            checks.append(("Memory 使用 < 85%", mem_data['total_mib'] < (10 * 1024 * 0.85)))  # 假設 10GB
        
        galera_status = self.get_galera_cluster_status()
        if galera_status["status"] == "success":
            ready = galera_status['galera'].get('ready', {})
            is_ready = list(ready.values())[0] if ready else 0
            checks.append(("Galera 就緒", is_ready == 1))
        
        for check_name, passed in checks:
            status = "✅" if passed else "⚠️ "
            print(f"{status} {check_name}")
        
        print("\n" + "="*100 + "\n")


def main():
    """主函數"""
    print("""
╔════════════════════════════════════════════════════════════════════════════════════╗
║     OpenFGA + MariaDB Galera Prometheus 監控工具                                  ║
║     使用 Prometheus metrics 進行實時監控（無需 kubectl）                          ║
╚════════════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # 獲取用戶輸入
    prometheus_url = input("請輸入 Prometheus 地址 (默認 http://localhost:9090): ").strip() or "http://localhost:9090"
    namespace = input("請輸入 Kubernetes namespace (默認 openfga-prod): ").strip() or "openfga-prod"
    
    print("\n選擇操作:")
    print("  1. 實時監控儀表板（一次）")
    print("  2. 持續監控（每 5 秒更新）")
    print("  3. 自定義更新間隔持續監控")
    print("  4. 監控摘要報告")
    
    choice = input("\n請選擇 (1/2/3/4): ").strip()
    
    monitor = PrometheusMonitor(prometheus_url, namespace)
    
    if choice == "1":
        monitor.print_dashboard(continuous=False)
    elif choice == "2":
        monitor.print_dashboard(interval=5, continuous=True)
    elif choice == "3":
        try:
            interval = int(input("請輸入更新間隔（秒）: ").strip())
            monitor.print_dashboard(interval=interval, continuous=True)
        except ValueError:
            print("❌ 無效的間隔值")
    elif choice == "4":
        monitor.print_summary_report()
    else:
        print("❌ 無效選擇")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已中止監控。")
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
