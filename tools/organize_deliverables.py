"""把本次作业的全部截图按类别整理到桌面的一个文件夹里"""
import os
import shutil

SRC = r"C:\Users\30816\Documents\deepseek-harness\default-workspace\imagegrab\测试截图"
ROOT = r"C:\Users\30816\Desktop\作业\5.Git与图片下载插件-提交材料"

# 分类结构：目标子目录 -> [(源文件, 目标文件名)]
PLAN = {
    "1-插件截图": [
        ("插件-01-详情页悬浮按钮.png", "1-详情页右下角-获取图片按钮.png"),
        ("插件-02-画廊页总览.png",     "2-图片画廊页-集中预览与勾选.png"),
        ("插件-04-下载进度.png",       "3-批量下载-进度提示.png"),
        ("插件-05-下载完成反馈.png",   "4-批量下载-完成结果反馈.png"),
        ("插件-06-弹窗.png",           "5-插件弹窗-平台识别与历史记录.png"),
    ],
    "2-推送到GitHub的截图": [
        ("GitHub-01-仓库首页.png",     "1-GitHub仓库首页.png"),
        ("GitHub-02-仓库文件列表.png", "2-仓库完整文件列表.png"),
        ("GitHub-03-提交记录.png",     "3-Git提交记录-4次提交.png"),
        ("GitHub-04-官网源码.png",     "4-仓库中的官网源码.png"),
    ],
    "3-GitHubPages线上官网截图": [
        ("线上-00-Pages官网首屏(带域名).png", "1-线上官网首屏(含域名地址).png"),
        ("线上-02-Pages官网整页.png",         "2-线上官网整页.png"),
        ("线上-03-Pages核心功能区.png",       "3-线上官网-核心功能.png"),
        ("线上-04-Pages安装步骤区.png",       "4-线上官网-安装步骤.png"),
        ("线上-05-Pages移动端.png",           "5-线上官网-移动端适配.png"),
    ],
    "4-官网本地预览截图(补充)": [
        ("官网-01-首屏.png",     "1-官网首屏.png"),
        ("官网-02-整页.png",     "2-官网桌面整页.png"),
        ("官网-03-平板.png",     "3-官网平板适配.png"),
        ("官网-04-手机.png",     "4-官网手机适配.png"),
        ("官网-05-手机菜单.png", "5-官网手机端汉堡菜单.png"),
    ],
}

if os.path.exists(ROOT):
    shutil.rmtree(ROOT)
os.makedirs(ROOT)

missing = []
for sub, items in PLAN.items():
    d = os.path.join(ROOT, sub)
    os.makedirs(d, exist_ok=True)
    for src_name, dst_name in items:
        src = os.path.join(SRC, src_name)
        if not os.path.exists(src):
            missing.append(src_name)
            continue
        shutil.copy2(src, os.path.join(d, dst_name))

# 文档一起放进去
for doc in ("提交信息.txt", "推送指南.md"):
    p = os.path.join(os.path.dirname(SRC), "提交材料", doc)
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(ROOT, doc))
src_guide = os.path.join(os.path.dirname(SRC), "推送指南.md")
if os.path.exists(src_guide):
    shutil.copy2(src_guide, os.path.join(ROOT, "GitHub推送与Pages发布指南.md"))

print("整理完成 ->", ROOT)
total = 0
for sub in sorted(os.listdir(ROOT)):
    p = os.path.join(ROOT, sub)
    if os.path.isdir(p):
        files = sorted(os.listdir(p))
        total += len(files)
        print(f"\n  [{sub}]  {len(files)} 张")
        for f in files:
            print(f"      - {f}  ({os.path.getsize(os.path.join(p, f))/1024:.0f} KB)")
    else:
        print(f"\n  {sub}  ({os.path.getsize(p)/1024:.0f} KB)")
print(f"\n截图合计：{total} 张")
if missing:
    print("缺失文件：", missing)
