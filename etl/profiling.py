import pandas as pd
import openpyxl

wb = openpyxl.load_workbook('data/raw/consumers-price-index-march-2026-quarter.xlsx',
                            read_only= True)
print(wb.sheetnames)

df_raw = pd.read_excel('data/raw/consumers-price-index-march-2026-quarter.xlsx',
                       sheet_name='1',
                       header=None)

print('Shape:', df_raw.shape)
print(df_raw.iloc[:12]) #show first 12 rows