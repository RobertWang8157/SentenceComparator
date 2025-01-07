import pandas as pd

# 读取 HTML 文件中的所有表格
tables = pd.read_html("/Users/johnny/train/tool/index.html")


# 将第一个表格转换为 DataFrame
df = tables[0]

# 将 DataFrame 写入 Excel 文件
df.to_excel('gatling_request_data.xlsx', index=False)
