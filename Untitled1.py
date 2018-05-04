import pandas, json
df= pandas.read_csv("/home/ubuntu/workspace/marxan/Marxan243/MarxanData_unix/andrew/Sample scenario/output/output_ssoln.txt").pivot(index='number',columns='planning_unit',values='planning_unit')
transposed = df[df.columns].apply(lambda x: ','.join(x.dropna().astype(int).astype(str)),axis=1)
ssoln = [[i,[int(n) for n in j.split(",")]] for (i,j) in transposed.items()]
print json.loads(json.dumps(ssoln))
