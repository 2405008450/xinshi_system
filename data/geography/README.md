# 地区数据来源

CSC Countries States Cities Database: https://github.com/dr5hn/countries-states-cities-database (ODbL 1.0, https://opendatacommons.org/licenses/odbl/1-0/)。派生目录 catalog.json.gz 以相同许可证提供。国家、一级行政区及城市使用数据源所提供的中文译名，缺失时保留原名。

中国大陆省市区补充来源：https://github.com/modood/Administrative-divisions-of-China (MIT)。大陆目录包含省、市、区县；全球数据并不保证每个国家的全部末级行政区，缺失信息支持手工录入。地区沿用数据源分类，不据此改变客户已有的国家或地区记录。

生成脚本 tools/build_geography_catalog.py；源文件放在忽略目录 tmp/geography。目录仅供地址录入参考，不自动改写历史客户数据。
