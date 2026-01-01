#!/usr/bin/env python3
"""
OpenFGA + MariaDB Galera 配置檢查和驗證工具
用於驗證部署是否符合高 RPS 設計規範
"""

import subprocess
import json
from typing import Dict, Tuple, List


class K8sChecker:
    """Kubernetes 集群檢查工具"""
    
    def __init__(self, namespace: str = "openfga-prod"):
        self.namespace = namespace
        self.checks = {}
    
    def run_command(self, cmd: str) -> Tuple[int, str, str]:
        """運行 kubectl 命令"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timeout"
        except Exception as e:
            return 1, "", str(e)
    
    def check_namespace(self) -> bool:
        """檢查 namespace 是否存在"""
        cmd = f"kubectl get namespace {self.namespace}"
        code, _, _ = self.run_command(cmd)
        return code == 0
    
    def check_pods(self) -> Dict:
        """檢查 Pod 狀態"""
        cmd = f"kubectl get pods -n {self.namespace} -o json"
        code, stdout, _ = self.run_command(cmd)
        
        if code != 0:
            return {"status": "error", "message": "Failed to get pods"}
        
        try:
            data = json.loads(stdout)
            pods = {}
            for pod in data.get("items", []):
                name = pod["metadata"]["name"]
                phase = pod["status"]["phase"]
                pods[name] = phase
            
            # 統計
            ready = sum(1 for p in pods.values() if p == "Running")
            total = len(pods)
            
            return {
                "status": "success",
                "total": total,
                "ready": ready,
                "pods": pods
            }
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON response"}
    
    def check_mysql_connections(self) -> Dict:
        """檢查 MySQL 連接數"""
        cmd = f"""
        kubectl exec -it mariadb-galera-0 -n {self.namespace} -- \
        mysql -e "SHOW STATUS LIKE 'Threads%';" 2>/dev/null | tail -3
        """
        code, stdout, _ = self.run_command(cmd)
        
        if code != 0:
            return {"status": "error", "message": "Cannot connect to MySQL"}
        
        lines = stdout.strip().split('\n')
        result = {}
        for line in lines:
            if 'Threads' in line:
                parts = line.split('\t')
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    result[key] = int(value) if value.isdigit() else value
        
        return {
            "status": "success",
            "connections": result
        }
    
    def check_galera_status(self) -> Dict:
        """檢查 Galera 集群狀態"""
        cmd = f"""
        kubectl exec -it mariadb-galera-0 -n {self.namespace} -- \
        mysql -e "SHOW STATUS LIKE 'wsrep_cluster_status';" 2>/dev/null | tail -1
        """
        code, stdout, _ = self.run_command(cmd)
        
        if code != 0:
            return {"status": "error", "message": "Cannot check Galera status"}
        
        line = stdout.strip()
        is_primary = "Primary" in line
        
        return {
            "status": "success",
            "cluster_healthy": is_primary,
            "output": line
        }
    
    def check_resources(self) -> Dict:
        """檢查資源使用情況"""
        cmd = f"kubectl top pods -n {self.namespace} --no-headers 2>/dev/null"
        code, stdout, _ = self.run_command(cmd)
        
        if code != 0:
            return {"status": "error", "message": "Metrics not available"}
        
        resources = {}
        for line in stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 3:
                    name = parts[0]
                    cpu = parts[1]
                    memory = parts[2]
                    resources[name] = {
                        "cpu": cpu,
                        "memory": memory
                    }
        
        return {
            "status": "success",
            "resources": resources
        }
    
    def print_report(self):
        """打印檢查報告"""
        print("\n" + "="*80)
        print("🔍 OpenFGA + MariaDB Galera 部署檢查報告")
        print("="*80)
        
        # 1. 檢查 namespace
        print("\n[1] Namespace 檢查")
        print("-" * 80)
        if self.check_namespace():
            print(f"✅ Namespace '{self.namespace}' 存在")
        else:
            print(f"❌ Namespace '{self.namespace}' 不存在")
            print("   解決方案: kubectl create namespace openfga-prod")
            return
        
        # 2. 檢查 Pod
        print("\n[2] Pod 狀態檢查")
        print("-" * 80)
        pod_check = self.check_pods()
        if pod_check["status"] == "success":
            print(f"✅ Pod 檢查成功")
            print(f"   總計: {pod_check['total']} Pod")
            print(f"   就緒: {pod_check['ready']} Pod")
            
            # 分類顯示
            galera_pods = [p for p in pod_check['pods'] if 'mariadb-galera' in p]
            openfga_pods = [p for p in pod_check['pods'] if 'openfga' in p]
            
            print(f"\n   MariaDB Galera ({len(galera_pods)}):")
            for pod, phase in [(p, pod_check['pods'][p]) for p in galera_pods]:
                status_icon = "✅" if phase == "Running" else "⏳" if phase == "Pending" else "❌"
                print(f"     {status_icon} {pod}: {phase}")
            
            print(f"\n   OpenFGA ({len(openfga_pods)}):")
            for pod, phase in [(p, pod_check['pods'][p]) for p in openfga_pods][:5]:
                status_icon = "✅" if phase == "Running" else "⏳" if phase == "Pending" else "❌"
                print(f"     {status_icon} {pod}: {phase}")
            
            if len(openfga_pods) > 5:
                print(f"     ... 和 {len(openfga_pods) - 5} 個其他 Pod")
        else:
            print(f"❌ {pod_check.get('message')}")
            return
        
        # 3. 檢查 MySQL 連接
        print("\n[3] MySQL 連接狀態")
        print("-" * 80)
        mysql_check = self.check_mysql_connections()
        if mysql_check["status"] == "success":
            print("✅ MySQL 連接正常")
            for key, value in mysql_check.get("connections", {}).items():
                print(f"   {key}: {value}")
        else:
            print(f"❌ {mysql_check.get('message')}")
        
        # 4. 檢查 Galera 狀態
        print("\n[4] Galera 集群狀態")
        print("-" * 80)
        galera_check = self.check_galera_status()
        if galera_check["status"] == "success":
            if galera_check["cluster_healthy"]:
                print("✅ Galera 集群健康 (Primary)")
            else:
                print("⚠️  Galera 集群異常")
                print(f"   輸出: {galera_check['output']}")
        else:
            print(f"❌ {galera_check.get('message')}")
        
        # 5. 檢查資源
        print("\n[5] 資源使用情況")
        print("-" * 80)
        resource_check = self.check_resources()
        if resource_check["status"] == "success":
            print("✅ 資源使用情況:")
            
            # 分類統計
            total_cpu = 0
            total_mem = 0
            
            for pod, resources in resource_check["resources"].items():
                cpu = resources["cpu"].rstrip('m')
                mem = resources["memory"].rstrip('Mi')
                
                try:
                    total_cpu += int(cpu)
                    total_mem += int(mem)
                except ValueError:
                    pass
                
                print(f"   {pod}:")
                print(f"     CPU: {resources['cpu']}, 記憶體: {resources['memory']}")
            
            print(f"\n   總計:")
            print(f"     CPU: {total_cpu}m ({total_cpu/1000:.1f} cores)")
            print(f"     記憶體: {total_mem}Mi ({total_mem/1024:.1f} Gi)")
        else:
            print(f"⚠️  {resource_check.get('message')}")
            print("   提示: 請確保已安裝 metrics-server")
        
        # 6. 檢查清單
        print("\n[6] 配置檢查清單")
        print("-" * 80)
        
        checklist = [
            ("Pod 副本數符合需求", 8, pod_check.get("ready", 0) >= 8 if pod_check["status"] == "success" else False),
            ("MariaDB Galera 集群就緒", 3, len([p for p in pod_check.get("pods", {}) if "mariadb" in p and pod_check["pods"][p] == "Running"]) >= 3 if pod_check["status"] == "success" else False),
            ("MySQL 連接可用", 1, mysql_check["status"] == "success"),
            ("Galera 集群健康", 1, galera_check.get("cluster_healthy", False)),
        ]
        
        all_pass = True
        for check_name, expected, result in checklist:
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}")
            if not result:
                all_pass = False
        
        # 總結
        print("\n" + "="*80)
        if all_pass and pod_check["ready"] >= 8:
            print("✅ 所有檢查通過！部署已就緒進行性能測試")
            print("\n建議的下一步:")
            print("  1. 運行連接池計算器: python connection_pool_calculator.py")
            print("  2. 執行性能基線測試")
            print("  3. 根據結果調整配置")
        else:
            print("⚠️  還有待解決的問題")
            print("\n建議的操作:")
            print("  1. 等待所有 Pod 就緒 (kubectl get pods -w)")
            print("  2. 檢查 Pod 日誌 (kubectl logs <pod-name> -n openfga-prod)")
            print("  3. 查看詳細信息 (kubectl describe pod <pod-name> -n openfga-prod)")
        
        print("="*80 + "\n")


def main():
    """主函數"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║     OpenFGA + MariaDB Galera 部署檢查工具                                   ║
║     驗證高 RPS 設計的部署就緒狀態                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # 提示用戶確認
    namespace = input("請輸入 OpenFGA namespace (默認 openfga-prod): ").strip() or "openfga-prod"
    
    print(f"\n正在檢查 namespace '{namespace}'...\n")
    
    # 運行檢查
    checker = K8sChecker(namespace)
    checker.print_report()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已中止檢查。")
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        print("   請確保已正確配置 kubectl 和 Kubernetes 集群連接")
