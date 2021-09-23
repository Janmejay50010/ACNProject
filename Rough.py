import json

RouterMetadataPath = './RouterMetadata.json'

A_dict = {'A': 3000}
B_dict = {'B' : 2000}

with open(RouterMetadataPath) as f:
    data = json.load(f)
    print(data)

data.update(B_dict)

with open(RouterMetadataPath, 'w') as f:
    json.dump(data, f)