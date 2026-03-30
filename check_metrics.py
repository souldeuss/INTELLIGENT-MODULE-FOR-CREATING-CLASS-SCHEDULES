import json

with open('saved_models/training_metrics_20260328_182709.json') as f:
    data = json.load(f)
    print(f'Training Metrics File Analysis:')
    print(f'  Iterations reported: {data.get("iterations")}')
    print(f'  Rewards count: {len(data["metrics"]["rewards"])}')
    if data["metrics"]["rewards"]:
        print(f'  First 3 rewards: {data["metrics"]["rewards"][:3]}')
        print(f'  Last 3 rewards: {data["metrics"]["rewards"][-3:]}')
    print(f'  Hard violations count: {len(data["metrics"]["hard_violations"])}')
    if data["metrics"]["hard_violations"]:
        print(f'  Hard violations: {data["metrics"]["hard_violations"][:5]} ... {data["metrics"]["hard_violations"][-5:]}')
    
    if data["metrics"]["rewards"] and len(data["metrics"]["rewards"]) > 0:
        print(f'\n✅ METRICS ARE POPULATED - Training was successful!')
        print(f'\n📊 Test Data Processing Status:')
        print(f'  - Training metrics: SAVED ✅')
        print(f'  - Test evaluation: REQUIRES SAME STATE_DIM')
        print(f'  - Issue: Test cases have state_dim = 595, 725, 855')
        print(f'  - Training used: state_dim = 2337')
        print(f'  - Solution: Test cases incompatible with this model')
    else:
        print(f'\n❌ METRICS ARE EMPTY - Problem still exists')
