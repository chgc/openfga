#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pod_rps_monitor.py - 自動監控每個 Pod 的 RPS 和容量使用率

功能：
1. 從 Prometheus 獲取實時 RPS 數據
2. 監控 Pod 資源使用情況
3. 計算容量使用百分比
4. 生成彩色報告
5. 告警過載 Pod

使用方法：
    # 確保 Prometheus port-forward 正在運行
    kubectl port-forward -n monitoring svc/prometheus 9090:9090 &
    
    # 運行監控器
    python3 pod_rps_monitor.py
    
    # 自定義參數
    python3 pod_rps_monitor.py --namespace openfga-prod --capacity 2000 --interval 10
"""

import subprocess
import json
import time
import argparse
import sys
from datetime import datetime
from typing import Dict, List, Optional


class Colors:
    """ANSI 顏色代碼"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


class PodRPSMonitor:
    """OpenFGA Pod RPS 容量監控器"""
    
    def __init__(
        self,
        namespace: str = "openfga-prod",
        theoretical_rps_per_pod: int = 2000,
        prometheus_url: str = "http://localhost:9090",
        app_label: str = "app=openfga"
    ):
        """
        初始化監控器
        
        Args:
            namespace: Kubernetes namespace
            theoretical_rps_per_pod: 每個 Pod 的理論最大 RPS
            prometheus_url: Prometheus 服務器 URL
            app_label: Pod 標籤選擇器
        """
        self.namespace = namespace
        self.theoretical_rps = theoretical_rps_per_pod
        self.prometheus_url = prometheus_url
        self.app_label = app_label
        self.previous_rps = {}
    
    def query_prometheus(self, query: str) -> Optional[List[Dict]]:
        """
        查詢 Prometheus
        
        Args:
            query: PromQL 查詢語句
            
        Returns:
            查詢結果列表，失敗返回 None
        """
        cmd = [
            "curl", "-s", "-G",
            f"{self.prometheus_url}/api/v1/query",
            "--data-urlencode", f"query={query}",
            "--max-time", "5"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return None
            
            data = json.loads(result.stdout)
            
            if data.get("status") == "success":
                return data["data"]["result"]
            
            return None
        
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            print(f"{Colors.RED}Error querying Prometheus: {e}{Colors.END}")
            return None
    
    def get_pod_rps(self) -> Dict[str, float]:
        """
        從 Prometheus 獲取每個 Pod 的當前 RPS
        
        Returns:
            {pod_name: rps} 字典
        """
        query = f'''
        sum by(pod) (
          rate(grpc_server_handled_total{{
            namespace="{self.namespace}",
            grpc_service="openfga.v1.OpenFGAService"
          }}[1m])
        )
        '''
        
        results = self.query_prometheus(query)
        
        if not results:
            return {}
        
        pod_rps = {}
        for item in results:
            pod_name = item["metric"]["pod"]
            rps = float(item["value"][1])
            pod_rps[pod_name] = rps
        
        return pod_rps
    
    def get_pod_error_rate(self) -> Dict[str, float]:
        """
        獲取每個 Pod 的錯誤率百分比
        
        Returns:
            {pod_name: error_rate_percent} 字典
        """
        query = f'''
        (
          sum by(pod) (
            rate(grpc_server_handled_total{{
              namespace="{self.namespace}",
              grpc_code!="OK"
            }}[1m])
          )
          /
          sum by(pod) (
            rate(grpc_server_handled_total{{
              namespace="{self.namespace}"
            }}[1m])
          )
        ) * 100
        '''
        
        results = self.query_prometheus(query)
        
        if not results:
            return {}
        
        pod_error_rate = {}
        for item in results:
            pod_name = item["metric"]["pod"]
            error_rate = float(item["value"][1])
            pod_error_rate[pod_name] = error_rate
        
        return pod_error_rate
    
    def get_pod_latency(self) -> Dict[str, Dict[str, float]]:
        """
        獲取每個 Pod 的延遲統計（p50, p99）
        
        Returns:
            {pod_name: {p50: value, p99: value}} 字典
        """
        pod_latency = {}
        
        # p50
        query_p50 = f'''
        histogram_quantile(0.5,
          sum by(pod, le) (
            rate(grpc_server_handling_seconds_bucket{{
              namespace="{self.namespace}",
              grpc_service="openfga.v1.OpenFGAService"
            }}[1m])
          )
        ) * 1000
        '''
        
        results_p50 = self.query_prometheus(query_p50)
        if results_p50:
            for item in results_p50:
                pod_name = item["metric"]["pod"]
                if pod_name not in pod_latency:
                    pod_latency[pod_name] = {}
                pod_latency[pod_name]["p50"] = float(item["value"][1])
        
        # p99
        query_p99 = f'''
        histogram_quantile(0.99,
          sum by(pod, le) (
            rate(grpc_server_handling_seconds_bucket{{
              namespace="{self.namespace}",
              grpc_service="openfga.v1.OpenFGAService"
            }}[1m])
          )
        ) * 1000
        '''
        
        results_p99 = self.query_prometheus(query_p99)
        if results_p99:
            for item in results_p99:
                pod_name = item["metric"]["pod"]
                if pod_name not in pod_latency:
                    pod_latency[pod_name] = {}
                pod_latency[pod_name]["p99"] = float(item["value"][1])
        
        return pod_latency
    
    def get_pod_resources(self) -> Dict[str, Dict[str, float]]:
        """
        獲取 Pod 資源使用率（CPU, Memory）
        
        Returns:
            {pod_name: {cpu_millicores: value, memory_mi: value}} 字典
        """
        cmd = [
            "kubectl", "top", "pods",
            "-n", self.namespace,
            "-l", self.app_label,
            "--no-headers"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return {}
            
            pod_resources = {}
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split()
                if len(parts) < 3:
                    continue
                
                pod_name = parts[0]
                cpu_str = parts[1].replace('m', '')
                memory_str_raw = parts[2]
                
                # Parse memory with proper unit handling
                try:
                    if 'Gi' in memory_str_raw:
                        memory = float(memory_str_raw.replace('Gi', '')) * 1024
                    else:
                        memory = float(memory_str_raw.replace('Mi', ''))
                    
                    cpu = float(cpu_str)
                    
                    pod_resources[pod_name] = {
                        'cpu_millicores': cpu,
                        'memory_mi': memory
                    }
                except (ValueError, IndexError) as e:
                    # Log parsing errors for debugging
                    print(f"{Colors.YELLOW}Warning: Failed to parse resources for pod {pod_name}: {e}{Colors.END}", file=sys.stderr)
                    continue
            
            return pod_resources
        
        except (subprocess.TimeoutExpired, Exception) as e:
            print(f"{Colors.RED}Error getting pod resources: {e}{Colors.END}")
            return {}
    
    def calculate_capacity_usage(self, current_rps: float) -> float:
        """
        計算容量使用百分比
        
        Args:
            current_rps: 當前 RPS
            
        Returns:
            容量使用百分比 (0-100+)
        """
        return (current_rps / self.theoretical_rps) * 100
    
    def get_status_indicator(self, capacity_pct: float, error_rate: float = 0) -> str:
        """
        根據容量使用率和錯誤率返回狀態指示器
        
        Args:
            capacity_pct: 容量使用百分比
            error_rate: 錯誤率百分比
            
        Returns:
            彩色狀態指示器字符串
        """
        if error_rate > 1.0:
            return f"{Colors.RED}🔴 CRITICAL{Colors.END}"
        
        if capacity_pct > 90:
            return f"{Colors.RED}🔴 OVERLOAD{Colors.END}"
        elif capacity_pct > 80:
            return f"{Colors.RED}🟠 HIGH{Colors.END}"
        elif capacity_pct > 60:
            return f"{Colors.YELLOW}🟡 MEDIUM{Colors.END}"
        else:
            return f"{Colors.GREEN}🟢 HEALTHY{Colors.END}"
    
    def calculate_rps_trend(self, pod_name: str, current_rps: float) -> str:
        """
        計算 RPS 趨勢
        
        Args:
            pod_name: Pod 名稱
            current_rps: 當前 RPS
            
        Returns:
            趨勢指示器 (↑, ↓, →)
        """
        if pod_name not in self.previous_rps:
            self.previous_rps[pod_name] = current_rps
            return "→"
        
        previous = self.previous_rps[pod_name]
        diff = current_rps - previous
        
        self.previous_rps[pod_name] = current_rps
        
        if abs(diff) < current_rps * 0.05:  # 5% 變化內視為穩定
            return "→"
        elif diff > 0:
            return f"{Colors.RED}↑{Colors.END}"
        else:
            return f"{Colors.GREEN}↓{Colors.END}"
    
    def print_header(self):
        """打印報告頭部"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*100}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}OpenFGA Pod RPS 容量監控報告{Colors.END}")
        print(f"{Colors.CYAN}{'='*100}{Colors.END}")
        print(f"{Colors.BOLD}時間:{Colors.END} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{Colors.BOLD}Namespace:{Colors.END} {self.namespace}")
        print(f"{Colors.BOLD}理論容量:{Colors.END} {self.theoretical_rps} RPS/Pod")
        print(f"{Colors.CYAN}{'-'*100}{Colors.END}\n")
    
    def print_pod_details(
        self,
        pod_name: str,
        rps: float,
        capacity_pct: float,
        resources: Dict[str, float],
        error_rate: float = 0,
        latency: Dict[str, float] = None
    ):
        """
        打印單個 Pod 的詳細信息
        
        Args:
            pod_name: Pod 名稱
            rps: 當前 RPS
            capacity_pct: 容量使用百分比
            resources: 資源使用情況
            error_rate: 錯誤率
            latency: 延遲統計
        """
        status = self.get_status_indicator(capacity_pct, error_rate)
        trend = self.calculate_rps_trend(pod_name, rps)
        
        print(f"{status} {Colors.BOLD}Pod:{Colors.END} {pod_name}")
        print(f"   {Colors.BOLD}當前 RPS:{Colors.END} {rps:>8.2f} {trend}")
        print(f"   {Colors.BOLD}容量使用:{Colors.END} {capacity_pct:>6.1f}%")
        
        if error_rate > 0:
            error_color = Colors.RED if error_rate > 1 else Colors.YELLOW if error_rate > 0.1 else Colors.GREEN
            print(f"   {Colors.BOLD}錯誤率:{Colors.END}   {error_color}{error_rate:>6.2f}%{Colors.END}")
        
        if latency:
            p50 = latency.get("p50", 0)
            p99 = latency.get("p99", 0)
            
            p50_color = Colors.GREEN if p50 < 50 else Colors.YELLOW if p50 < 100 else Colors.RED
            p99_color = Colors.GREEN if p99 < 150 else Colors.YELLOW if p99 < 300 else Colors.RED
            
            print(f"   {Colors.BOLD}延遲 p50:{Colors.END}  {p50_color}{p50:>6.1f}ms{Colors.END}")
            print(f"   {Colors.BOLD}延遲 p99:{Colors.END}  {p99_color}{p99:>6.1f}ms{Colors.END}")
        
        cpu = resources.get('cpu_millicores', 0)
        memory = resources.get('memory_mi', 0)
        
        cpu_color = Colors.GREEN if cpu < 1000 else Colors.YELLOW if cpu < 1500 else Colors.RED
        mem_color = Colors.GREEN if memory < 512 else Colors.YELLOW if memory < 1024 else Colors.RED
        
        print(f"   {Colors.BOLD}CPU:{Colors.END}        {cpu_color}{cpu:>6.0f}m{Colors.END}")
        print(f"   {Colors.BOLD}Memory:{Colors.END}     {mem_color}{memory:>6.0f}Mi{Colors.END}")
        
        # 警告信息
        if capacity_pct > 80:
            print(f"   {Colors.RED}{Colors.BOLD}⚠️  警告: Pod 接近容量上限!{Colors.END}")
        if error_rate > 1:
            print(f"   {Colors.RED}{Colors.BOLD}⚠️  警告: 錯誤率過高!{Colors.END}")
        
        print()
    
    def print_summary(self, pod_rps: Dict[str, float]):
        """
        打印總結信息
        
        Args:
            pod_rps: {pod_name: rps} 字典
        """
        if not pod_rps:
            print(f"{Colors.RED}無數據{Colors.END}")
            return
        
        total_rps = sum(pod_rps.values())
        avg_rps = total_rps / len(pod_rps)
        max_rps = max(pod_rps.values())
        min_rps = min(pod_rps.values())
        
        cluster_capacity = self.theoretical_rps * len(pod_rps)
        cluster_usage_pct = (total_rps / cluster_capacity) * 100
        
        print(f"{Colors.CYAN}{'-'*100}{Colors.END}")
        print(f"{Colors.BOLD}集群總結:{Colors.END}")
        print(f"  {Colors.BOLD}總 RPS:{Colors.END}          {total_rps:>10.2f}")
        print(f"  {Colors.BOLD}平均 RPS/Pod:{Colors.END}   {avg_rps:>10.2f}")
        print(f"  {Colors.BOLD}最高 RPS:{Colors.END}        {max_rps:>10.2f}")
        print(f"  {Colors.BOLD}最低 RPS:{Colors.END}        {min_rps:>10.2f}")
        print(f"  {Colors.BOLD}負載不均衡係數:{Colors.END} {max_rps/avg_rps if avg_rps > 0 else 0:>10.2f}x")
        print(f"  {Colors.BOLD}集群總容量:{Colors.END}     {cluster_capacity:>10.0f} RPS")
        
        usage_color = Colors.GREEN if cluster_usage_pct < 60 else Colors.YELLOW if cluster_usage_pct < 80 else Colors.RED
        print(f"  {Colors.BOLD}集群容量使用:{Colors.END}   {usage_color}{cluster_usage_pct:>9.1f}%{Colors.END}")
        
        print(f"{Colors.CYAN}{'='*100}{Colors.END}\n")
    
    def print_report(
        self,
        pod_rps: Dict[str, float],
        pod_resources: Dict[str, Dict[str, float]],
        pod_error_rate: Dict[str, float] = None,
        pod_latency: Dict[str, Dict[str, float]] = None
    ):
        """
        打印完整監控報告
        
        Args:
            pod_rps: Pod RPS 數據
            pod_resources: Pod 資源使用數據
            pod_error_rate: Pod 錯誤率數據
            pod_latency: Pod 延遲數據
        """
        self.print_header()
        
        if not pod_rps:
            print(f"{Colors.RED}❌ 無法獲取 RPS 數據{Colors.END}")
            print(f"{Colors.YELLOW}請檢查:{Colors.END}")
            print(f"  1. Prometheus 是否正在運行")
            print(f"  2. Port-forward 是否設置: kubectl port-forward -n monitoring svc/prometheus 9090:9090")
            print(f"  3. OpenFGA Pods 是否正在運行")
            return
        
        # 按 RPS 降序排序
        sorted_pods = sorted(pod_rps.items(), key=lambda x: x[1], reverse=True)
        
        for pod_name, rps in sorted_pods:
            capacity_pct = self.calculate_capacity_usage(rps)
            resources = pod_resources.get(pod_name, {})
            error_rate = pod_error_rate.get(pod_name, 0) if pod_error_rate else 0
            latency = pod_latency.get(pod_name) if pod_latency else None
            
            self.print_pod_details(
                pod_name, rps, capacity_pct, resources,
                error_rate, latency
            )
        
        self.print_summary(pod_rps)
    
    def run(self, interval: int = 10, include_latency: bool = True):
        """
        持續監控
        
        Args:
            interval: 更新間隔（秒）
            include_latency: 是否包含延遲統計（可能較慢）
        """
        print(f"{Colors.BOLD}{Colors.GREEN}啟動 OpenFGA Pod RPS 監控器...{Colors.END}")
        print(f"{Colors.YELLOW}按 Ctrl+C 停止{Colors.END}\n")
        print(f"更新間隔: {interval} 秒")
        print(f"Prometheus: {self.prometheus_url}")
        
        try:
            while True:
                pod_rps = self.get_pod_rps()
                pod_resources = self.get_pod_resources()
                pod_error_rate = self.get_pod_error_rate()
                pod_latency = self.get_pod_latency() if include_latency else None
                
                self.print_report(
                    pod_rps, pod_resources,
                    pod_error_rate, pod_latency
                )
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}監控已停止{Colors.END}")
            sys.exit(0)


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description="OpenFGA Pod RPS 容量監控器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 默認配置
  %(prog)s
  
  # 自定義 namespace 和容量
  %(prog)s --namespace openfga-prod --capacity 2000
  
  # 更快的更新間隔（不包含延遲統計）
  %(prog)s --interval 5 --no-latency
  
  # 自定義 Prometheus URL
  %(prog)s --prometheus http://prometheus.monitoring.svc:9090

注意:
  確保 Prometheus port-forward 正在運行:
  kubectl port-forward -n monitoring svc/prometheus 9090:9090
        """
    )
    
    parser.add_argument(
        "--namespace", "-n",
        default="openfga-prod",
        help="Kubernetes namespace (默認: openfga-prod)"
    )
    
    parser.add_argument(
        "--capacity", "-c",
        type=int,
        default=2000,
        help="理論 RPS 容量每個 Pod (默認: 2000)"
    )
    
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=10,
        help="更新間隔秒數 (默認: 10)"
    )
    
    parser.add_argument(
        "--prometheus", "-p",
        default="http://localhost:9090",
        help="Prometheus URL (默認: http://localhost:9090)"
    )
    
    parser.add_argument(
        "--app-label", "-l",
        default="app=openfga",
        help="Pod 標籤選擇器 (默認: app=openfga)"
    )
    
    parser.add_argument(
        "--no-latency",
        action="store_true",
        help="不包含延遲統計（更快）"
    )
    
    args = parser.parse_args()
    
    monitor = PodRPSMonitor(
        namespace=args.namespace,
        theoretical_rps_per_pod=args.capacity,
        prometheus_url=args.prometheus,
        app_label=args.app_label
    )
    
    monitor.run(
        interval=args.interval,
        include_latency=not args.no_latency
    )


if __name__ == "__main__":
    main()
