"""把本次作业的全部截图 + 说明文档整理到 桌面\\作业\\提交材料\\考核3"""
import os
import shutil

# 分类好的成品（上一步生成）
SRC_ROOT = r"C:\Users\30816\Desktop\作业\5.Git与图片下载插件-提交材料"
# 目标：提交材料 下新建「考核3」
DST_ROOT = r"C:\Users\30816\Desktop\作业\提交材料\考核3"

assert os.path.isdir(SRC_ROOT), f"源目录不存在: {SRC_ROOT}"

if os.path.exists(DST_ROOT):
    shutil.rmtree(DST_ROOT)
os.makedirs(DST_ROOT)

count = 0
for name in sorted(os.listdir(SRC_ROOT)):
    s = os.path.join(SRC_ROOT, name)
    d = os.path.join(DST_ROOT, name)
    if os.path.isdir(s):
        shutil.copytree(s, d)
        n = len([f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))])
        count += n
        print(f"  [{name}]  {n} 张")
    else:
        shutil.copy2(s, d)
        print(f"  {name}  ({os.path.getsize(d)/1024:.0f} KB)")

print(f"\n目标目录: {DST_ROOT}")
print(f"截图合计: {count} 张")
