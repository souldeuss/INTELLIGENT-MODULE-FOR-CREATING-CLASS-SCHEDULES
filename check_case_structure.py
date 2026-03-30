import json

# Check training case (used first during training)
with open('data/dataset_compatible_1000/cases/case_777.json') as f:
    case777 = json.load(f)
    print(f'Training case (777):')
    print(f'  Keys: {list(case777.keys())}')
    print(f'  Groups: {len(case777["groups"])}')
    print(f'  Teachers: {len(case777["teachers"])}')
    print(f'  Classrooms: {len(case777["classrooms"])}')
    if "timeslots" in case777:
        print(f'  Timeslots: {len(case777["timeslots"])}')
    if "config" in case777:
        print(f'  Config: {case777["config"]}')

print()

# Check test case (state_dim=855)
with open('data/dataset_compatible_1000/cases/case_931.json') as f:
    case931 = json.load(f)
    print(f'Test case (931, state_dim=855):')
    print(f'  Keys: {list(case931.keys())}')
    print(f'  Groups: {len(case931["groups"])}')
    print(f'  Teachers: {len(case931["teachers"])}')
    print(f'  Classrooms: {len(case931["classrooms"])}')
    if "timeslots" in case931:
        print(f'  Timeslots: {len(case931["timeslots"])}')
    if "config" in case931:
        print(f'  Config: {case931["config"]}')

print()

# Check test case (state_dim=595)
with open('data/dataset_compatible_1000/cases/case_162.json') as f:
    case162 = json.load(f)
    print(f'Test case (162, state_dim=595):')
    print(f'  Keys: {list(case162.keys())}')
    print(f'  Groups: {len(case162["groups"])}')
    print(f'  Teachers: {len(case162["teachers"])}')
    print(f'  Classrooms: {len(case162["classrooms"])}')
    if "timeslots" in case162:
        print(f'  Timeslots: {len(case162["timeslots"])}')
    if "config" in case162:
        print(f'  Config: {case162["config"]}')
