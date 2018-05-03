import pandas
df = pandas.read_csv("/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/andrew/PNG Scenario/output/output_ssoln.txt",nrows=10)
print df.to_json(orient='split') 
print df.to_json(orient='records') 
print df.to_json(orient='index') 
print df.to_json(orient='columns') 
print df.to_json(orient='values') 
