#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用户提交记录测试脚本

@Description: 测试基于用户ID的提交记录获取功能，查看能获得哪些信息
"""

import json
from datetime import datetime
from user_commits import (
    get_user_info, 
    get_user_commits_directly,
    get_user_events
)

def print_separator(title="", char="=", length=80):
    """打印分隔线"""
    if title:
        title_line = f" {title} "
        padding = (length - len(title_line)) // 2
        print(char * padding + title_line + char * padding)
    else:
        print(char * length)

def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB"]
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.1f} {units[unit_index]}"

def test_user_commits(user_id):
    """测试用户提交记录获取"""
    
    print_separator("用户提交记录测试", "=")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试用户ID: {user_id}")
    print()
    
    # 1. 获取用户基本信息
    print_separator("1. 用户基本信息", "-")
    user_info = get_user_info(user_id)
    if not user_info:
        print("❌ 无法获取用户信息，请检查用户ID是否正确")
        return
    
    print(f"用户ID: {user_info['id']}")
    print(f"用户名: {user_info['username']}")
    print(f"姓名: {user_info['name']}")
    print(f"邮箱: {user_info.get('email', '未提供')}")
    print(f"注册时间: {user_info.get('created_at', '未知')}")
    print(f"最后活动: {user_info.get('last_activity_on', '未知')}")
    print(f"用户状态: {user_info.get('state', '未知')}")
    print()
    
    # 2. 获取用户活动事件
    print_separator("2. 用户活动事件分析", "-")
    events = get_user_events(user_id)
    print(f"获取到 {len(events)} 个推送相关事件")
    
    if events:
        # 分析事件
        project_ids = set()
        event_dates = []
        
        for event in events:
            project_id = event.get('project_id')
            if project_id:
                project_ids.add(project_id)
            
            created_at = event.get('created_at')
            if created_at:
                event_dates.append(created_at)
        
        print(f"涉及项目数量: {len(project_ids)}")
        if event_dates:
            print(f"最早事件: {min(event_dates)}")
            print(f"最新事件: {max(event_dates)}")
        
        # 显示前5个事件的详情
        print("\n最近5个推送事件:")
        for i, event in enumerate(events[:5]):
            print(f"  {i+1}. {event.get('created_at', 'Unknown')} - {event.get('action_name', 'Unknown')}")
            print(f"     项目: {event.get('project', {}).get('name', 'Unknown')} (ID: {event.get('project_id', 'Unknown')})")
            push_data = event.get('push_data', {})
            if push_data:
                print(f"     提交数: {push_data.get('commit_count', 1)}")
                print(f"     分支: {push_data.get('ref', 'Unknown')}")
    else:
        print("⚠️  未找到推送事件，可能用户最近没有推送活动")
    print()
    
    # 3. 获取提交记录
    print_separator("3. 提交记录获取", "-")
    commits_by_project = get_user_commits_directly(user_id)
    
    if not commits_by_project:
        print("❌ 未找到提交记录")
        return
    
    # 统计信息
    total_commits = sum(len(data['commits']) for data in commits_by_project.values())
    total_projects = len(commits_by_project)
    
    print(f"✅ 成功获取提交记录")
    print(f"涉及项目数: {total_projects}")
    print(f"总提交数: {total_commits}")
    print()
    
    # 4. 详细项目和提交信息
    print_separator("4. 详细项目和提交信息", "-")
    
    for project_id, project_data in commits_by_project.items():
        project_info = project_data['project_info']
        commits = project_data['commits']
        
        print_separator(f"项目: {project_info['name']}", "·")
        
        # 项目基本信息
        print("📂 项目信息:")
        print(f"  ID: {project_info['id']}")
        print(f"  名称: {project_info['name']}")
        print(f"  完整路径: {project_info.get('path_with_namespace', 'Unknown')}")
        print(f"  命名空间: {project_info.get('namespace', 'Unknown')}")
        print(f"  描述: {project_info.get('description', '无描述')}")
        print(f"  可见性: {project_info.get('visibility', 'Unknown')}")
        print(f"  默认分支: {project_info.get('default_branch', 'main')}")
        print(f"  项目总提交数: {project_info.get('commit_count', 0)}")
        print(f"  仓库大小: {format_size(project_info.get('repository_size', 0))}")
        print(f"  创建时间: {project_info.get('created_at', '未知')}")
        print(f"  最后活动: {project_info.get('last_activity_at', '未知')}")
        if project_info.get('web_url'):
            print(f"  项目链接: {project_info['web_url']}")
        
        # 用户在此项目的提交
        print(f"\n💻 用户在此项目的提交 ({len(commits)} 个):")
        
        if commits:
            # 按时间排序显示最近的5个提交
            sorted_commits = sorted(commits, key=lambda x: x.get('committed_date', ''), reverse=True)
            
            for i, commit in enumerate(sorted_commits[:5]):
                print(f"  {i+1}. {commit.get('committed_date', 'Unknown')[:19]}")
                print(f"     提交ID: {commit['short_id']}")
                print(f"     标题: {commit['title']}")
                print(f"     作者: {commit['author_name']} <{commit['author_email']}>")
                if len(commit['message']) > 100:
                    print(f"     消息: {commit['message'][:100]}...")
                else:
                    print(f"     消息: {commit['message']}")
                if commit.get('web_url'):
                    print(f"     链接: {commit['web_url']}")
                print()
            
            if len(commits) > 5:
                print(f"  ... 还有 {len(commits) - 5} 个提交未显示")
        
        print()
    
    # 5. 数据摘要
    print_separator("5. 数据摘要", "-")
    
    # 计算时间范围
    all_commit_dates = []
    all_emails = set()
    
    for project_data in commits_by_project.values():
        for commit in project_data['commits']:
            if commit.get('committed_date'):
                all_commit_dates.append(commit['committed_date'])
            if commit.get('author_email'):
                all_emails.add(commit['author_email'])
    
    print("📊 提交统计:")
    print(f"  总项目数: {total_projects}")
    print(f"  总提交数: {total_commits}")
    print(f"  使用的邮箱: {', '.join(all_emails) if all_emails else '未知'}")
    
    if all_commit_dates:
        all_commit_dates.sort()
        print(f"  最早提交: {all_commit_dates[0][:19]}")
        print(f"  最新提交: {all_commit_dates[-1][:19]}")
    
    # 按项目统计
    print(f"\n📈 按项目统计:")
    project_stats = []
    for project_id, project_data in commits_by_project.items():
        project_info = project_data['project_info']
        commits = project_data['commits']
        project_stats.append({
            'name': project_info['name'],
            'commits': len(commits)
        })
    
    project_stats.sort(key=lambda x: x['commits'], reverse=True)
    for stat in project_stats:
        print(f"  {stat['name']}: {stat['commits']} 个提交")
    
    print()
    print_separator("测试完成", "=")

def main():
    """主函数"""
    print("GitLab 用户提交记录测试工具")
    print("=" * 50)
    
    while True:
        try:
            user_input = input("\n请输入要测试的用户ID (输入 'quit' 退出): ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("退出测试")
                break
            
            if not user_input:
                print("请输入有效的用户ID")
                continue
            
            try:
                user_id = int(user_input)
            except ValueError:
                print("用户ID必须是数字")
                continue
            
            print()
            test_user_commits(user_id)
            
        except KeyboardInterrupt:
            print("\n\n测试被中断")
            break
        except Exception as e:
            print(f"\n测试过程中出错: {str(e)}")

if __name__ == "__main__":
    main() 