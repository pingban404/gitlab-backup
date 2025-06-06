#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用户提交记录导出模块

@Author: 您的名字
@Email: 您的邮箱
@Created: 2024-12-21
@License: MIT
@Version: 1.0.0
@Description: 导出指定用户的提交记录，用于法律材料
"""

import requests
import json
import csv
import os
from datetime import datetime
from pathlib import Path
from config import GITLAB_URL, PRIVATE_TOKEN, OUTPUT_DIR
from file_operations import load_projects_file

def get_user_info(user_id):
    """获取用户基本信息"""
    url = f"{GITLAB_URL}/api/v4/users/{user_id}"
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"获取用户信息失败: {response.text}")
            return None
    except Exception as e:
        print(f"获取用户信息时出错: {str(e)}")
        return None

def get_current_user():
    """获取当前认证用户信息"""
    url = f"{GITLAB_URL}/api/v4/user"
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"获取当前用户信息失败: {response.text}")
            return None
    except Exception as e:
        print(f"获取当前用户信息时出错: {str(e)}")
        return None

def get_all_users():
    """获取所有用户列表"""
    url = f"{GITLAB_URL}/api/v4/users"
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    params = {"per_page": 100}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"获取用户列表失败: {response.text}")
            return None
    except Exception as e:
        print(f"获取用户列表时出错: {str(e)}")
        return None

def get_project_commits(project_id, user_id=None, since=None, until=None):
    """获取项目的提交记录"""
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/repository/commits"
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    params = {
        "per_page": 100,
        "all": "true"
    }
    
    if user_id:
        # 先获取用户信息来获取邮箱
        user_info = get_user_info(user_id)
        if user_info and user_info.get('email'):
            params["author_email"] = user_info['email']
    
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    
    all_commits = []
    page = 1
    
    try:
        while True:
            params["page"] = page
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                commits = response.json()
                if not commits:  # 没有更多提交
                    break
                all_commits.extend(commits)
                page += 1
                
                # 避免无限循环，设置最大页数
                if page > 100:
                    break
            else:
                print(f"获取项目 {project_id} 提交记录失败: {response.text}")
                break
                
    except Exception as e:
        print(f"获取提交记录时出错: {str(e)}")
    
    return all_commits

def get_user_events(user_id, since=None, until=None):
    """获取用户的所有活动事件"""
    url = f"{GITLAB_URL}/api/v4/users/{user_id}/events"
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    params = {
        "per_page": 100
        # 不限制action类型，获取所有事件
    }
    
    if since:
        params["after"] = since
    if until:
        params["before"] = until
    
    all_events = []
    page = 1
    
    try:
        while True:
            params["page"] = page
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                events = response.json()
                if not events:  # 没有更多事件
                    break
                # 过滤出推送相关的事件
                push_events = [e for e in events if e.get('action_name') in ['pushed to', 'pushed new']]
                all_events.extend(push_events)
                page += 1
                
                # 限制页数以提高速度
                if page > 20:
                    break
            else:
                print(f"获取用户事件失败: {response.text}")
                break
                
    except Exception as e:
        print(f"获取用户事件时出错: {str(e)}")
    
    return all_events

def get_project_details(project_id):
    """获取项目的详细信息"""
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}"
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"获取项目 {project_id} 详情失败: {response.text}")
            return None
    except Exception as e:
        print(f"获取项目详情时出错: {str(e)}")
        return None

def get_commits_in_range(project_id, commit_from, commit_to, user_email=None, max_commits=10):
    """获取指定范围内的提交"""
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/repository/commits"
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    params = {
        "per_page": max_commits,
        "since": commit_from,
        "until": commit_to
    }
    
    commits = []
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            all_commits = response.json()
            for commit in all_commits:
                # 如果有邮箱信息，验证提交者
                if user_email:
                    if (commit.get('author_email') == user_email or 
                        commit.get('committer_email') == user_email):
                        commit_detail = get_commit_details(project_id, commit['id'])
                        if commit_detail:
                            commits.append(commit_detail)
                else:
                    # 没有邮箱信息，获取所有提交详情
                    commit_detail = get_commit_details(project_id, commit['id'])
                    if commit_detail:
                        commits.append(commit_detail)
    except Exception as e:
        print(f"获取提交范围时出错: {str(e)}")
    
    return commits

def get_user_commits_directly(user_id, since=None, until=None):
    """直接通过用户ID获取提交记录（基于用户活动事件）"""
    
    # 获取用户信息
    user_info = get_user_info(user_id)
    if not user_info:
        print(f"无法获取用户 {user_id} 的信息")
        return {}
    
    print(f"正在直接获取用户 {user_info['name']} ({user_info['username']}) 的提交记录...")
    
    # 获取用户的推送事件
    events = get_user_events(user_id, since, until)
    
    commits_by_project = {}
    processed_commits = set()  # 避免重复处理同一个提交
    
    print(f"正在分析 {len(events)} 个用户活动事件...")
    
    for event in events:
        if event.get('action_name') in ['pushed to', 'pushed new']:
            project_id = event.get('project_id')
            if not project_id:
                continue
                
            # 获取项目详细信息（如果还没获取过）
            if project_id not in commits_by_project:
                print(f"正在获取项目 ID {project_id} 的详细信息...")
                project_detail = get_project_details(project_id)
                if not project_detail:
                    continue
                
                # 增强项目信息
                enhanced_project_info = {
                    'id': project_detail['id'],
                    'name': project_detail['name'],
                    'path': project_detail['path'],
                    'path_with_namespace': project_detail['path_with_namespace'],
                    'namespace': project_detail.get('namespace', {}).get('name', 'Unknown'),
                    'namespace_path': project_detail.get('namespace', {}).get('path', 'Unknown'),
                    'description': project_detail.get('description', '无描述'),
                    'visibility': project_detail.get('visibility', 'Unknown'),
                    'web_url': project_detail.get('web_url', ''),
                    'created_at': project_detail.get('created_at', '未知'),
                    'last_activity_at': project_detail.get('last_activity_at', '未知'),
                    'default_branch': project_detail.get('default_branch', 'main'),
                    'commit_count': project_detail.get('statistics', {}).get('commit_count', '未知'),
                    'repository_size': project_detail.get('statistics', {}).get('repository_size', '未知')
                }
                
                commits_by_project[project_id] = {
                    'project_info': enhanced_project_info,
                    'commits': []
                }
                
                print(f"  发现项目: {project_detail['name']}")
            
            # 从推送事件中提取提交信息
            push_data = event.get('push_data', {})
            commit_to = push_data.get('commit_to')
            commit_count = push_data.get('commit_count', 1)
            
            # 处理主要提交（commit_to）
            if commit_to and f"{project_id}:{commit_to}" not in processed_commits:
                commit_detail = get_commit_details(project_id, commit_to)
                if commit_detail:
                    # 验证提交确实属于该用户
                    if (commit_detail.get('author_email') == user_info.get('email') or 
                        commit_detail.get('committer_email') == user_info.get('email') or
                        not user_info.get('email')):  # 如果没有邮箱信息，信任事件
                        commits_by_project[project_id]['commits'].append(commit_detail)
                        processed_commits.add(f"{project_id}:{commit_to}")
            
            # 如果事件中有提交范围信息，尝试获取更多提交
            if commit_count > 1:
                commit_from = push_data.get('commit_from')
                if commit_from and commit_to:
                    # 获取范围内的提交（限制最多10个避免过多请求）
                    range_commits = get_commits_in_range(project_id, commit_from, commit_to, user_info.get('email'), max_commits=10)
                    for commit_detail in range_commits:
                        commit_id = commit_detail['id']
                        if f"{project_id}:{commit_id}" not in processed_commits:
                            commits_by_project[project_id]['commits'].append(commit_detail)
                            processed_commits.add(f"{project_id}:{commit_id}")
    
    # 统计结果
    total_commits = sum(len(data['commits']) for data in commits_by_project.values())
    print(f"直接获取完成：在 {len(commits_by_project)} 个项目中找到 {total_commits} 个提交")
    
    # 如果通过事件API找到的提交较少，提供提示
    if total_commits < 10 and user_info.get('email'):
        print("提示：如果提交数量较少，可能是因为事件API只保留最近的活动")
        print("如需获取更完整的历史记录，建议使用功能3进行邮箱搜索")
    
    return commits_by_project

def get_user_commits_by_email(user_email, since=None, until=None):
    """通过用户邮箱搜索所有项目的提交记录"""
    
    # 获取项目列表
    projects_data = load_projects_file()
    if not projects_data:
        print("无法加载项目列表")
        return {}
    
    commits_by_project = {}
    
    print(f"正在通过邮箱 {user_email} 搜索提交记录...")
    
    for project in projects_data['projects'][:10]:  # 限制只搜索前10个项目以提高速度
        project_id = project['id']
        project_name = project['name']
        
        print(f"正在搜索项目: {project_name} (ID: {project_id})")
        
        # 使用邮箱搜索该项目的提交
        url = f"{GITLAB_URL}/api/v4/projects/{project_id}/repository/commits"
        headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
        params = {
            "per_page": 100,
            "author_email": user_email
        }
        
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                commits = response.json()
                if commits:
                    commits_by_project[project_id] = {
                        'project_info': project,
                        'commits': []
                    }
                    
                    for commit in commits:
                        commit_detail = get_commit_details(project_id, commit['id'])
                        if commit_detail:
                            commits_by_project[project_id]['commits'].append(commit_detail)
                    
                    print(f"  找到 {len(commits)} 个提交")
            
        except Exception as e:
            print(f"搜索项目 {project_name} 时出错: {str(e)}")
    
    return commits_by_project

def get_user_commits_by_email_enhanced(user_email, since=None, until=None):
    """通过用户邮箱搜索所有项目的提交记录（增强版本）"""
    
    # 获取项目列表
    projects_data = load_projects_file()
    if not projects_data:
        print("无法加载项目列表")
        return {}
    
    commits_by_project = {}
    
    print(f"正在通过邮箱 {user_email} 搜索提交记录（增强模式）...")
    
    for project in projects_data['projects'][:15]:  # 增加到15个项目
        project_id = project['id']
        project_name = project['name']
        
        print(f"正在搜索项目: {project_name} (ID: {project_id})")
        
        # 使用邮箱搜索该项目的提交
        url = f"{GITLAB_URL}/api/v4/projects/{project_id}/repository/commits"
        headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
        params = {
            "per_page": 100,
            "author_email": user_email
        }
        
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                commits = response.json()
                if commits:
                    # 获取项目详细信息
                    project_detail = get_project_details(project_id)
                    if project_detail:
                        # 使用增强的项目信息
                        enhanced_project_info = {
                            'id': project_detail['id'],
                            'name': project_detail['name'],
                            'path': project_detail['path'],
                            'path_with_namespace': project_detail['path_with_namespace'],
                            'namespace': project_detail.get('namespace', {}).get('name', 'Unknown'),
                            'namespace_path': project_detail.get('namespace', {}).get('path', 'Unknown'),
                            'description': project_detail.get('description', '无描述'),
                            'visibility': project_detail.get('visibility', 'Unknown'),
                            'web_url': project_detail.get('web_url', ''),
                            'created_at': project_detail.get('created_at', '未知'),
                            'last_activity_at': project_detail.get('last_activity_at', '未知'),
                            'default_branch': project_detail.get('default_branch', 'main'),
                            'commit_count': project_detail.get('statistics', {}).get('commit_count', 0),
                            'repository_size': project_detail.get('statistics', {}).get('repository_size', 0)
                        }
                    else:
                        enhanced_project_info = project
                    
                    commits_by_project[project_id] = {
                        'project_info': enhanced_project_info,
                        'commits': []
                    }
                    
                    for commit in commits:
                        commit_detail = get_commit_details(project_id, commit['id'])
                        if commit_detail:
                            commits_by_project[project_id]['commits'].append(commit_detail)
                    
                    print(f"  找到 {len(commits)} 个提交")
            
        except Exception as e:
            print(f"搜索项目 {project_name} 时出错: {str(e)}")
    
    return commits_by_project

def get_commit_details(project_id, commit_sha):
    """获取单个提交的详细信息"""
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/repository/commits/{commit_sha}"
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"获取提交详情时出错: {str(e)}")
        return None

def get_commit_diff(project_id, commit_sha):
    """获取提交的文件变更信息"""
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/repository/commits/{commit_sha}/diff"
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"获取提交差异时出错: {str(e)}")
        return None

def export_user_commits_to_json(user_id, output_file, since=None, until=None):
    """将用户提交记录导出为JSON格式"""
    
    # 获取用户信息
    user_info = get_user_info(user_id)
    if not user_info:
        print(f"无法获取用户 {user_id} 的信息")
        return False
    
    # 获取项目列表
    projects_data = load_projects_file()
    if not projects_data:
        print("无法加载项目列表")
        return False
    
    export_data = {
        "export_info": {
            "export_time": datetime.now().isoformat(),
            "gitlab_url": GITLAB_URL,
            "export_type": "user_commits",
            "user_id": user_id,
            "time_range": {
                "since": since,
                "until": until
            }
        },
        "user_info": user_info,
        "projects": []
    }
    
    print(f"正在导出用户 {user_info['name']} ({user_info['username']}) 的提交记录...")
    
    for project in projects_data['projects']:
        project_id = project['id']
        project_name = project['name']
        
        print(f"正在处理项目: {project_name} (ID: {project_id})")
        
        # 获取该项目中用户的提交
        commits = get_project_commits(project_id, user_id, since, until)
        
        if commits:
            # 获取每个提交的详细信息
            detailed_commits = []
            for commit in commits:
                commit_detail = get_commit_details(project_id, commit['id'])
                if commit_detail:
                    # 获取文件变更信息
                    diff_info = get_commit_diff(project_id, commit['id'])
                    commit_detail['file_changes'] = diff_info
                    detailed_commits.append(commit_detail)
            
            project_data = {
                "project_info": project,
                "commits_count": len(detailed_commits),
                "commits": detailed_commits
            }
            export_data['projects'].append(project_data)
            print(f"  找到 {len(detailed_commits)} 个提交")
        else:
            print(f"  未找到提交记录")
    
    # 保存到文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n用户提交记录已导出到: {output_file}")
        return True
    except Exception as e:
        print(f"保存文件时出错: {str(e)}")
        return False

def export_user_commits_to_csv(user_id, output_file, since=None, until=None):
    """将用户提交记录导出为CSV格式"""
    
    # 获取用户信息
    user_info = get_user_info(user_id)
    if not user_info:
        print(f"无法获取用户 {user_id} 的信息")
        return False
    
    # 获取项目列表
    projects_data = load_projects_file()
    if not projects_data:
        print("无法加载项目列表")
        return False
    
    csv_data = []
    
    print(f"正在导出用户 {user_info['name']} ({user_info['username']}) 的提交记录...")
    
    for project in projects_data['projects']:
        project_id = project['id']
        project_name = project['name']
        
        print(f"正在处理项目: {project_name} (ID: {project_id})")
        
        # 获取该项目中用户的提交
        commits = get_project_commits(project_id, user_id, since, until)
        
        if commits:
            for commit in commits:
                commit_detail = get_commit_details(project_id, commit['id'])
                if commit_detail:
                    # 获取文件变更信息
                    diff_info = get_commit_diff(project_id, commit['id'])
                    
                    # 统计文件变更
                    files_changed = len(diff_info) if diff_info else 0
                    additions = sum(d.get('additions', 0) for d in diff_info) if diff_info else 0
                    deletions = sum(d.get('deletions', 0) for d in diff_info) if diff_info else 0
                    
                    csv_row = {
                        'project_id': project_id,
                        'project_name': project_name,
                        'project_namespace': project['namespace'],
                        'commit_id': commit_detail['id'],
                        'commit_short_id': commit_detail['short_id'],
                        'commit_title': commit_detail['title'],
                        'commit_message': commit_detail['message'],
                        'author_name': commit_detail['author_name'],
                        'author_email': commit_detail['author_email'],
                        'committer_name': commit_detail['committer_name'],
                        'committer_email': commit_detail['committer_email'],
                        'created_at': commit_detail['created_at'],
                        'committed_date': commit_detail['committed_date'],
                        'files_changed': files_changed,
                        'additions': additions,
                        'deletions': deletions,
                        'web_url': commit_detail.get('web_url', '')
                    }
                    csv_data.append(csv_row)
            
            print(f"  找到 {len([c for c in commits])} 个提交")
    
    # 保存到CSV文件
    try:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            if csv_data:
                writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
                writer.writeheader()
                writer.writerows(csv_data)
        
        print(f"\n用户提交记录已导出到: {output_file}")
        print(f"总共导出 {len(csv_data)} 个提交记录")
        return True
    except Exception as e:
        print(f"保存CSV文件时出错: {str(e)}")
        return False

def generate_legal_report(user_id, output_file, since=None, until=None):
    """生成法律用途的HTML报告"""
    
    # 获取用户信息
    user_info = get_user_info(user_id)
    if not user_info:
        print(f"无法获取用户 {user_id} 的信息")
        return False
    
    # 获取项目列表
    projects_data = load_projects_file()
    if not projects_data:
        print("无法加载项目列表")
        return False
    
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>用户提交记录法律报告 - {user_info['name']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .user-info {{ margin: 20px 0; }}
        .project {{ margin: 20px 0; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }}
        .project h3 {{ color: #2c3e50; margin-top: 0; }}
        .project h4 {{ color: #34495e; margin-top: 20px; }}
        .commit {{ margin: 10px 0; padding: 15px; background-color: #f9f9f9; border-radius: 3px; border-left: 4px solid #3498db; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
        .commit-id {{ font-family: monospace; font-size: 0.8em; background-color: #ecf0f1; padding: 2px 5px; border-radius: 3px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; font-weight: bold; width: 200px; }}
        .project-info th {{ background-color: #e8f4f8; }}
        .commit-stats th {{ background-color: #e8f8f5; }}
        .summary {{ background-color: #fef9e7; padding: 15px; border-radius: 5px; margin-top: 20px; }}
        .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 0.9em; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        pre {{ background-color: #f8f9fa; padding: 10px; border-radius: 3px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>用户提交记录法律报告</h1>
        <p><strong>导出时间：</strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>数据来源：</strong>{GITLAB_URL}</p>
        <p><strong>时间范围：</strong>{since or '所有时间'} 至 {until or '现在'}</p>
    </div>
    
    <div class="user-info">
        <h2>用户信息</h2>
        <table>
            <tr><th>用户ID</th><td>{user_info['id']}</td></tr>
            <tr><th>用户名</th><td>{user_info['username']}</td></tr>
            <tr><th>姓名</th><td>{user_info['name']}</td></tr>
            <tr><th>邮箱</th><td>{user_info.get('email', '未提供')}</td></tr>
            <tr><th>注册时间</th><td>{user_info.get('created_at', '未知')}</td></tr>
            <tr><th>最后活动</th><td>{user_info.get('last_activity_on', '未知')}</td></tr>
        </table>
    </div>
    
    <div class="projects">
        <h2>项目提交记录</h2>
"""
    
    total_commits = 0
    
    for project in projects_data['projects']:
        project_id = project['id']
        project_name = project['name']
        
        print(f"正在处理项目: {project_name} (ID: {project_id})")
        
        # 获取该项目中用户的提交
        commits = get_project_commits(project_id, user_id, since, until)
        
        if commits:
            html_content += f"""
        <div class="project">
            <h3>{project_name} (ID: {project_id})</h3>
            <p><strong>命名空间：</strong>{project['namespace']}</p>
            <p><strong>提交数量：</strong>{len(commits)}</p>
            
            <div class="commits">
"""
            
            for commit in commits:
                commit_detail = get_commit_details(project_id, commit['id'])
                if commit_detail:
                    # 获取文件变更信息
                    diff_info = get_commit_diff(project_id, commit['id'])
                    files_changed = len(diff_info) if diff_info else 0
                    
                    html_content += f"""
                <div class="commit">
                    <h4>{commit_detail['title']}</h4>
                    <p class="commit-id"><strong>提交ID：</strong>{commit_detail['id']}</p>
                    <p class="timestamp"><strong>提交时间：</strong>{commit_detail['committed_date']}</p>
                    <p><strong>作者：</strong>{commit_detail['author_name']} &lt;{commit_detail['author_email']}&gt;</p>
                    <p><strong>提交者：</strong>{commit_detail['committer_name']} &lt;{commit_detail['committer_email']}&gt;</p>
                    <p><strong>修改文件数：</strong>{files_changed}</p>
                    <p><strong>提交消息：</strong></p>
                    <pre>{commit_detail['message']}</pre>
                </div>
"""
            
            html_content += """
            </div>
        </div>
"""
            total_commits += len(commits)
            print(f"  找到 {len(commits)} 个提交")
    
    html_content += f"""
    </div>
    
    <div class="summary">
        <h2>统计摘要</h2>
        <p><strong>总提交数：</strong>{total_commits}</p>
        <p><strong>涉及项目数：</strong>{len([p for p in projects_data['projects']])}</p>
    </div>
    
    <div class="footer">
        <p><em>此报告由 GitLab 项目导出工具生成，数据来源于 {GITLAB_URL}</em></p>
        <p><em>报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
    </div>
</body>
</html>
"""
    
    # 保存HTML文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n法律报告已生成: {output_file}")
        print(f"总共包含 {total_commits} 个提交记录")
        return True
    except Exception as e:
        print(f"生成HTML报告时出错: {str(e)}")
        return False

def quick_export_current_user(format_type="html", since=None, until=None):
    """快速导出当前用户的提交记录"""
    
    # 获取当前用户信息
    user_info = get_current_user()
    if not user_info:
        print("无法获取当前用户信息，请检查Token是否有效")
        return False
    
    user_id = user_info['id']
    username = user_info['username']
    
    print(f"正在导出用户 {user_info['name']} ({username}) 的提交记录...")
    
    # 确保输出目录存在
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if format_type == "json":
        filename = f"current_user_{username}_commits_{timestamp}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        return export_user_commits_to_json(user_id, filepath, since, until)
    elif format_type == "csv":
        filename = f"current_user_{username}_commits_{timestamp}.csv"
        filepath = os.path.join(OUTPUT_DIR, filename)
        return export_user_commits_to_csv(user_id, filepath, since, until)
    elif format_type == "html":
        filename = f"current_user_{username}_legal_report_{timestamp}.html"
        filepath = os.path.join(OUTPUT_DIR, filename)
        return generate_legal_report(user_id, filepath, since, until)
    else:
        print("不支持的导出格式")
        return False

def quick_export_user_by_id(user_id, format_type="html", since=None, until=None):
    """快速导出指定用户ID的提交记录"""
    
    # 获取用户信息
    user_info = get_user_info(user_id)
    if not user_info:
        print(f"无法获取用户 {user_id} 的信息，请检查用户ID是否正确")
        return False
    
    username = user_info['username']
    
    print(f"正在导出用户 {user_info['name']} ({username}) 的提交记录...")
    
    # 确保输出目录存在
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if format_type == "json":
        filename = f"user_{user_id}_{username}_commits_{timestamp}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        return export_user_commits_direct_to_json(user_id, filepath, since, until)
    elif format_type == "csv":
        filename = f"user_{user_id}_{username}_commits_{timestamp}.csv"
        filepath = os.path.join(OUTPUT_DIR, filename)
        return export_user_commits_direct_to_csv(user_id, filepath, since, until)
    elif format_type == "html":
        filename = f"user_{user_id}_{username}_legal_report_{timestamp}.html"
        filepath = os.path.join(OUTPUT_DIR, filename)
        return generate_user_legal_report_direct(user_id, filepath, since, until)
    else:
        print("不支持的导出格式")
        return False

def export_user_commits_direct_to_json(user_id, output_file, since=None, until=None):
    """直接导出用户提交记录为JSON格式（高效版本）"""
    
    # 获取用户信息
    user_info = get_user_info(user_id)
    if not user_info:
        print(f"无法获取用户 {user_id} 的信息")
        return False
    
    # 直接获取用户的提交记录
    commits_by_project = get_user_commits_directly(user_id, since, until)
    
    export_data = {
        "export_info": {
            "export_time": datetime.now().isoformat(),
            "gitlab_url": GITLAB_URL,
            "export_type": "user_commits_direct",
            "user_id": user_id,
            "time_range": {
                "since": since,
                "until": until
            }
        },
        "user_info": user_info,
        "projects": []
    }
    
    total_commits = 0
    for project_id, project_data in commits_by_project.items():
        # 获取每个提交的详细信息（包括文件变更）
        detailed_commits = []
        for commit in project_data['commits']:
            # 获取文件变更信息
            diff_info = get_commit_diff(project_id, commit['id'])
            commit['file_changes'] = diff_info
            detailed_commits.append(commit)
        
        project_export_data = {
            "project_info": project_data['project_info'],
            "commits_count": len(detailed_commits),
            "commits": detailed_commits
        }
        export_data['projects'].append(project_export_data)
        total_commits += len(detailed_commits)
    
    # 保存到文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n用户提交记录已导出到: {output_file}")
        print(f"总共导出 {total_commits} 个提交记录，涉及 {len(commits_by_project)} 个项目")
        return True
    except Exception as e:
        print(f"保存文件时出错: {str(e)}")
        return False

def export_user_commits_direct_to_csv(user_id, output_file, since=None, until=None):
    """直接导出用户提交记录为CSV格式（高效版本）"""
    
    # 获取用户信息
    user_info = get_user_info(user_id)
    if not user_info:
        print(f"无法获取用户 {user_id} 的信息")
        return False
    
    # 直接获取用户的提交记录
    commits_by_project = get_user_commits_directly(user_id, since, until)
    
    csv_data = []
    
    for project_id, project_data in commits_by_project.items():
        project_info = project_data['project_info']
        
        for commit in project_data['commits']:
            # 获取文件变更信息
            diff_info = get_commit_diff(project_id, commit['id'])
            
            # 统计文件变更
            files_changed = len(diff_info) if diff_info else 0
            additions = sum(d.get('additions', 0) for d in diff_info) if diff_info else 0
            deletions = sum(d.get('deletions', 0) for d in diff_info) if diff_info else 0
            
            csv_row = {
                'project_id': project_id,
                'project_name': project_info['name'],
                'project_path': project_info.get('path', project_info['name']),
                'project_full_path': project_info.get('path_with_namespace', f"{project_info.get('namespace', 'Unknown')}/{project_info['name']}"),
                'project_namespace': project_info.get('namespace', 'Unknown'),
                'project_namespace_path': project_info.get('namespace_path', 'Unknown'),
                'project_description': project_info.get('description', '无描述'),
                'project_visibility': project_info.get('visibility', 'Unknown'),
                'project_web_url': project_info.get('web_url', ''),
                'project_created_at': project_info.get('created_at', '未知'),
                'project_default_branch': project_info.get('default_branch', 'main'),
                'project_total_commits': project_info.get('commit_count', 0),
                'project_repository_size': project_info.get('repository_size', 0),
                'commit_id': commit['id'],
                'commit_short_id': commit['short_id'],
                'commit_title': commit['title'],
                'commit_message': commit['message'],
                'author_name': commit['author_name'],
                'author_email': commit['author_email'],
                'committer_name': commit['committer_name'],
                'committer_email': commit['committer_email'],
                'created_at': commit['created_at'],
                'committed_date': commit['committed_date'],
                'files_changed': files_changed,
                'additions': additions,
                'deletions': deletions,
                'commit_web_url': commit.get('web_url', '')
            }
            csv_data.append(csv_row)
    
    # 保存到CSV文件
    try:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            if csv_data:
                writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
                writer.writeheader()
                writer.writerows(csv_data)
        
        print(f"\n用户提交记录已导出到: {output_file}")
        print(f"总共导出 {len(csv_data)} 个提交记录，涉及 {len(commits_by_project)} 个项目")
        return True
    except Exception as e:
        print(f"保存CSV文件时出错: {str(e)}")
        return False

def generate_user_legal_report_direct(user_id, output_file, since=None, until=None):
    """直接生成用户法律用途的HTML报告（高效版本）"""
    
    # 获取用户信息
    user_info = get_user_info(user_id)
    if not user_info:
        print(f"无法获取用户 {user_id} 的信息")
        return False
    
    # 直接获取用户的提交记录
    commits_by_project = get_user_commits_directly(user_id, since, until)
    
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>用户提交记录法律报告 - {user_info['name']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .user-info {{ margin: 20px 0; }}
        .project {{ margin: 20px 0; border: 1px solid #ddd; padding: 15px; }}
        .commit {{ margin: 10px 0; padding: 10px; background-color: #f9f9f9; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
        .commit-id {{ font-family: monospace; font-size: 0.8em; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>用户提交记录法律报告</h1>
        <p><strong>导出时间：</strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>数据来源：</strong>{GITLAB_URL}</p>
        <p><strong>时间范围：</strong>{since or '所有时间'} 至 {until or '现在'}</p>
        <p><strong>导出方法：</strong>直接通过用户事件API获取</p>
    </div>
    
    <div class="user-info">
        <h2>用户信息</h2>
        <table>
            <tr><th>用户ID</th><td>{user_info['id']}</td></tr>
            <tr><th>用户名</th><td>{user_info['username']}</td></tr>
            <tr><th>姓名</th><td>{user_info['name']}</td></tr>
            <tr><th>邮箱</th><td>{user_info.get('email', '未提供')}</td></tr>
            <tr><th>注册时间</th><td>{user_info.get('created_at', '未知')}</td></tr>
            <tr><th>最后活动</th><td>{user_info.get('last_activity_on', '未知')}</td></tr>
        </table>
    </div>
    
    <div class="projects">
        <h2>项目提交记录</h2>
"""
    
    total_commits = 0
    
    for project_id, project_data in commits_by_project.items():
        project_info = project_data['project_info']
        commits = project_data['commits']
        
        if commits:
            # 计算文件变更统计
            total_files_changed = 0
            total_additions = 0
            total_deletions = 0
            
            for commit in commits:
                diff_info = get_commit_diff(project_id, commit['id'])
                if diff_info:
                    total_files_changed += len(diff_info)
                    total_additions += sum(d.get('additions', 0) for d in diff_info)
                    total_deletions += sum(d.get('deletions', 0) for d in diff_info)
            
            html_content += f"""
        <div class="project">
            <h3>{project_info['name']} (ID: {project_id})</h3>
            <table class="project-info">
                <tr><th>项目路径</th><td>{project_info.get('path_with_namespace', 'Unknown')}</td></tr>
                <tr><th>命名空间</th><td>{project_info.get('namespace', 'Unknown')}</td></tr>
                <tr><th>项目描述</th><td>{project_info.get('description', '无描述')}</td></tr>
                <tr><th>可见性</th><td>{project_info.get('visibility', 'Unknown')}</td></tr>
                <tr><th>默认分支</th><td>{project_info.get('default_branch', 'main')}</td></tr>
                <tr><th>项目创建时间</th><td>{project_info.get('created_at', '未知')}</td></tr>
                <tr><th>最后活动时间</th><td>{project_info.get('last_activity_at', '未知')}</td></tr>
                <tr><th>项目总提交数</th><td>{project_info.get('commit_count', 0)}</td></tr>
                <tr><th>仓库大小</th><td>{project_info.get('repository_size', 0)} 字节</td></tr>
                <tr><th>项目链接</th><td><a href="{project_info.get('web_url', '')}" target="_blank">{project_info.get('web_url', '')}</a></td></tr>
            </table>
            
            <h4>用户在此项目的提交统计</h4>
            <table class="commit-stats">
                <tr><th>用户提交数</th><td>{len(commits)}</td></tr>
                <tr><th>总文件变更数</th><td>{total_files_changed}</td></tr>
                <tr><th>总新增行数</th><td style="color: green;">+{total_additions}</td></tr>
                <tr><th>总删除行数</th><td style="color: red;">-{total_deletions}</td></tr>
                <tr><th>净变更行数</th><td style="color: {'green' if total_additions - total_deletions >= 0 else 'red'};">{'+' if total_additions - total_deletions >= 0 else ''}{total_additions - total_deletions}</td></tr>
            </table>
            
            <div class="commits">
"""
            
            for commit in commits:
                # 获取文件变更信息
                diff_info = get_commit_diff(project_id, commit['id'])
                files_changed = len(diff_info) if diff_info else 0
                
                html_content += f"""
                <div class="commit">
                    <h4>{commit['title']}</h4>
                    <p class="commit-id"><strong>提交ID：</strong>{commit['id']}</p>
                    <p class="timestamp"><strong>提交时间：</strong>{commit['committed_date']}</p>
                    <p><strong>作者：</strong>{commit['author_name']} &lt;{commit['author_email']}&gt;</p>
                    <p><strong>提交者：</strong>{commit['committer_name']} &lt;{commit['committer_email']}&gt;</p>
                    <p><strong>修改文件数：</strong>{files_changed}</p>
                    <p><strong>提交消息：</strong></p>
                    <pre>{commit['message']}</pre>
                </div>
"""
            
            html_content += """
            </div>
        </div>
"""
            total_commits += len(commits)
    
    html_content += f"""
    </div>
    
    <div class="summary">
        <h2>统计摘要</h2>
        <p><strong>总提交数：</strong>{total_commits}</p>
        <p><strong>涉及项目数：</strong>{len(commits_by_project)}</p>
    </div>
    
    <div class="footer">
        <p><em>此报告由 GitLab 项目导出工具生成，数据来源于 {GITLAB_URL}</em></p>
        <p><em>报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
    </div>
</body>
</html>
"""
    
    # 保存HTML文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n法律报告已生成: {output_file}")
        print(f"总共包含 {total_commits} 个提交记录，涉及 {len(commits_by_project)} 个项目")
        return True
    except Exception as e:
        print(f"生成HTML报告时出错: {str(e)}")
        return False