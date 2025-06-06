import time
from datetime import datetime
from tqdm import tqdm
from gitlab_api import start_export, check_export_status, download_export
from file_operations import ensure_output_dir, get_project_info, load_projects_file, save_projects_to_file
from config import OUTPUT_DIR
import os

def show_menu():
    """显示主菜单"""
    print("\n" + "=" * 50)
    print("GitLab 项目工具")
    print("=" * 50)
    print("1. 查询项目列表")
    print("2. 导出项目")
    print("3. 导出用户提交记录")
    print("4. 快速导出当前用户提交记录")
    print("5. 快速导出指定用户ID提交记录")
    print("0. 退出")
    print("=" * 50)
    choice = input("\n请选择功能 (0-5): ")
    return choice

def handle_menu_choice(choice):
    """处理菜单选择"""
    if choice == "1":
        from gitlab_api import get_projects
        projects, success = get_projects()
        if success and input("\n是否将项目列表保存到本地文件？(y/n): ").lower() == 'y':
            save_projects_to_file(projects)
    elif choice == "2":
        project_id = select_project()
        if project_id:
            try:
                if export_project(project_id):
                    print("项目导出流程完成")
                else:
                    print("项目导出流程失败")
            except ValueError:
                print("请输入有效的项目ID（数字）")
    elif choice == "3":
        handle_user_commits_export()
    elif choice == "4":
        handle_quick_export_current_user()
    elif choice == "5":
        handle_quick_export_user_by_id()
    elif choice == "0":
        print("退出程序")
        return False
    else:
        print("无效的选择，请重新输入")
    return True

def select_project():
    """从项目列表中选择项目"""
    data = load_projects_file()
    if not data:
        print("\n正在自动获取项目列表...")
        from gitlab_api import get_projects
        projects, success = get_projects(save_automatically=True)
        if not success:
            return None
        from file_operations import save_projects_to_file
        save_projects_to_file(projects)
        data = load_projects_file()
        if not data:
            return None
            
    projects = data['projects']
    print("\n项目列表：")
    print("=" * 80)
    print(f"{'ID':<8} {'项目名称':<30} {'命名空间':<20} {'最后活动时间':<20}")
    print("-" * 80)
    
    for project in projects:
        last_activity = project.get('last_activity_at', '未知')
        if last_activity != '未知':
            last_activity = last_activity.split('T')[0]  # 只显示日期部分
        print(f"{project['id']:<8} {project['name']:<30} {project['namespace']:<20} {last_activity:<20}")
    print("=" * 80)
    
    while True:
        try:
            project_id = input("\n请输入要导出的项目ID (输入0返回): ")
            if project_id == '0':
                return None
                
            project_id = int(project_id)
            # 验证项目ID是否存在
            if any(project['id'] == project_id for project in projects):
                return project_id
            else:
                print("无效的项目ID，请重新输入")
        except ValueError:
            print("请输入有效的项目ID（数字）")

def export_project(project_id):
    """导出项目的完整流程"""
    ensure_output_dir()
    
    if not start_export(project_id):
        return False
    
    print("\n正在等待导出完成...")
    with tqdm(total=100, desc="导出进度") as pbar:
        while True:
            status = check_export_status(project_id)
            if status == "finished":
                pbar.update(100 - pbar.n)
                break
            elif status == "failed":
                print("\n导出失败")
                return False
            elif status == "none":
                print("\n项目未找到或无权访问")
                return False
            
            # 更新进度条（假设导出过程大约需要30秒）
            if pbar.n < 90:  # 保留10%给最后的完成状态
                pbar.update(1)
            time.sleep(0.3)  # 更频繁地更新进度条
    
    project_info = get_project_info(project_id)
    if not project_info:
        print("无法获取项目信息")
        return False
    
    success = download_export(project_id, project_info, OUTPUT_DIR)
    
    # 导出完成后删除项目列表文件
    try:
        from config import GITLAB_URL
        domain = GITLAB_URL.split('://')[1].rstrip('/').replace(':', '_')
        filename = f"{domain}.yaml"
        filepath = os.path.join("projects", filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print(f"删除项目列表文件时出错: {str(e)}")
    
    return success

def show_users_list():
    """显示用户列表供选择"""
    from user_commits import get_all_users
    
    users = get_all_users()
    if not users:
        print("无法获取用户列表")
        return None
    
    print("\n用户列表：")
    print("=" * 80)
    print(f"{'ID':<8} {'用户名':<20} {'姓名':<25} {'邮箱':<25}")
    print("-" * 80)
    
    for user in users[:20]:  # 只显示前20个用户
        print(f"{user['id']:<8} {user['username']:<20} {user.get('name', '未设置'):<25} {user.get('email', '未提供'):<25}")
    
    if len(users) > 20:
        print(f"... 还有 {len(users) - 20} 个用户未显示")
    
    print("=" * 80)
    
    while True:
        try:
            user_input = input("\n请输入用户ID或用户名 (输入0返回): ")
            if user_input == '0':
                return None
            
            # 检查是否为数字（用户ID）
            if user_input.isdigit():
                user_id = int(user_input)
                # 验证用户ID是否存在
                if any(user['id'] == user_id for user in users):
                    return user_id
                else:
                    print("无效的用户ID，请重新输入")
            else:
                # 检查用户名
                for user in users:
                    if user['username'].lower() == user_input.lower():
                        return user['id']
                print("无效的用户名，请重新输入")
        except ValueError:
            print("请输入有效的用户ID（数字）或用户名")

def handle_user_commits_export():
    """处理用户提交记录导出"""
    ensure_output_dir()
    
    # 检查项目列表文件是否存在
    data = load_projects_file()
    if not data:
        print("\n正在自动获取项目列表...")
        from gitlab_api import get_projects
        projects, success = get_projects(save_automatically=True)
        if not success:
            print("无法获取项目列表，请先使用功能1查询项目列表")
            return
        save_projects_to_file(projects)
    
    # 选择用户
    user_id = show_users_list()
    if not user_id:
        return
    
    # 选择导出格式
    print("\n请选择导出格式：")
    print("1. JSON格式（完整数据）")
    print("2. CSV格式（表格数据）")
    print("3. HTML报告（法律用途）")
    
    format_choice = input("\n请选择格式 (1-3): ")
    
    # 时间范围选择（可选）
    print("\n时间范围设置（可选，直接回车跳过）：")
    since = input("开始时间 (YYYY-MM-DD): ").strip()
    until = input("结束时间 (YYYY-MM-DD): ").strip()
    
    # 验证时间格式
    if since:
        try:
            datetime.strptime(since, '%Y-%m-%d')
            since = since + "T00:00:00Z"
        except ValueError:
            print("开始时间格式错误，将忽略")
            since = None
    
    if until:
        try:
            datetime.strptime(until, '%Y-%m-%d')
            until = until + "T23:59:59Z"
        except ValueError:
            print("结束时间格式错误，将忽略")
            until = None
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        if format_choice == "1":
            # JSON格式
            filename = f"user_{user_id}_commits_{timestamp}.json"
            filepath = os.path.join(OUTPUT_DIR, filename)
            
            from user_commits import export_user_commits_to_json
            success = export_user_commits_to_json(user_id, filepath, since, until)
            
        elif format_choice == "2":
            # CSV格式
            filename = f"user_{user_id}_commits_{timestamp}.csv"
            filepath = os.path.join(OUTPUT_DIR, filename)
            
            from user_commits import export_user_commits_to_csv
            success = export_user_commits_to_csv(user_id, filepath, since, until)
            
        elif format_choice == "3":
            # HTML报告
            filename = f"user_{user_id}_legal_report_{timestamp}.html"
            filepath = os.path.join(OUTPUT_DIR, filename)
            
            from user_commits import generate_legal_report
            success = generate_legal_report(user_id, filepath, since, until)
            
        else:
            print("无效的格式选择")
            return
        
        if success:
            print("\n用户提交记录导出完成！")
            print(f"文件保存位置: {filepath}")
        else:
            print("\n用户提交记录导出失败")
            
    except Exception as e:
        print(f"导出过程中出错: {str(e)}")

def handle_quick_export_user_by_id():
    """处理指定用户ID的快速导出"""
    ensure_output_dir()
    
    # 检查项目列表文件是否存在
    data = load_projects_file()
    if not data:
        print("\n正在自动获取项目列表...")
        from gitlab_api import get_projects
        projects, success = get_projects(save_automatically=True)
        if not success:
            print("无法获取项目列表，请先使用功能1查询项目列表")
            return
        save_projects_to_file(projects)
    
    # 输入用户ID
    while True:
        try:
            user_input = input("\n请输入用户ID (输入0返回): ").strip()
            if user_input == '0':
                return
            
            user_id = int(user_input)
            if user_id <= 0:
                print("用户ID必须是正整数，请重新输入")
                continue
            break
        except ValueError:
            print("请输入有效的用户ID（数字）")
    
    # 先验证用户是否存在
    from user_commits import get_user_info
    user_info = get_user_info(user_id)
    if not user_info:
        print(f"用户ID {user_id} 不存在或无权限访问")
        return
    
    print(f"\n找到用户: {user_info['name']} ({user_info['username']})")
    
    # 选择导出格式
    print("\n请选择导出格式：")
    print("1. JSON格式（完整数据）")
    print("2. CSV格式（表格数据）")  
    print("3. HTML报告（法律用途）[推荐]")
    
    format_choice = input("\n请选择格式 (1-3，默认3): ").strip()
    if not format_choice:
        format_choice = "3"
    
    # 时间范围选择（可选）
    print("\n时间范围设置（可选，直接回车跳过）：")
    since = input("开始时间 (YYYY-MM-DD): ").strip()
    until = input("结束时间 (YYYY-MM-DD): ").strip()
    
    # 验证时间格式
    if since:
        try:
            datetime.strptime(since, '%Y-%m-%d')
            since = since + "T00:00:00Z"
        except ValueError:
            print("开始时间格式错误，将忽略")
            since = None
    
    if until:
        try:
            datetime.strptime(until, '%Y-%m-%d')
            until = until + "T23:59:59Z"
        except ValueError:
            print("结束时间格式错误，将忽略")
            until = None
    
    # 确定导出格式
    format_map = {"1": "json", "2": "csv", "3": "html"}
    format_type = format_map.get(format_choice, "html")
    
    try:
        from user_commits import quick_export_user_by_id
        success = quick_export_user_by_id(user_id, format_type, since, until)
        
        if success:
            print(f"\n用户 {user_info['name']} 的提交记录导出完成！")
        else:
            print(f"\n用户 {user_info['name']} 的提交记录导出失败")
            
    except Exception as e:
        print(f"导出过程中出错: {str(e)}")

def handle_quick_export_current_user():
    """处理当前用户快速导出"""
    ensure_output_dir()
    
    # 检查项目列表文件是否存在
    data = load_projects_file()
    if not data:
        print("\n正在自动获取项目列表...")
        from gitlab_api import get_projects
        projects, success = get_projects(save_automatically=True)
        if not success:
            print("无法获取项目列表，请先使用功能1查询项目列表")
            return
        save_projects_to_file(projects)
    
    # 选择导出格式
    print("\n请选择导出格式：")
    print("1. JSON格式（完整数据）")
    print("2. CSV格式（表格数据）")  
    print("3. HTML报告（法律用途）[推荐]")
    
    format_choice = input("\n请选择格式 (1-3，默认3): ").strip()
    if not format_choice:
        format_choice = "3"
    
    # 时间范围选择（可选）
    print("\n时间范围设置（可选，直接回车跳过）：")
    since = input("开始时间 (YYYY-MM-DD): ").strip()
    until = input("结束时间 (YYYY-MM-DD): ").strip()
    
    # 验证时间格式
    if since:
        try:
            datetime.strptime(since, '%Y-%m-%d')
            since = since + "T00:00:00Z"
        except ValueError:
            print("开始时间格式错误，将忽略")
            since = None
    
    if until:
        try:
            datetime.strptime(until, '%Y-%m-%d')
            until = until + "T23:59:59Z"
        except ValueError:
            print("结束时间格式错误，将忽略")
            until = None
    
    # 确定导出格式
    format_map = {"1": "json", "2": "csv", "3": "html"}
    format_type = format_map.get(format_choice, "html")
    
    try:
        from user_commits import quick_export_current_user
        success = quick_export_current_user(format_type, since, until)
        
        if success:
            print("\n当前用户提交记录导出完成！")
        else:
            print("\n当前用户提交记录导出失败")
            
    except Exception as e:
        print(f"导出过程中出错: {str(e)}") 