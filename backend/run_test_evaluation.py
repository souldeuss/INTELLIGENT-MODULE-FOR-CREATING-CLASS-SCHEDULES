#!/usr/bin/env python3
"""
Standalone evaluation script for testing the trained model on test dataset.
Validates that test data is processed and generates evaluation statistics.

KEY ISSUE DETECTED:
- Training cases have varying state_dim (2337, others)
- Test cases also have varying state_dim (855, 595, 725)
- Model must handle variable input dimensions or there's a problem
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Ensure backend module is importable
sys.path.insert(0, str(Path(__file__).parent))

from app.core.environment_v2 import TimetablingEnvironmentV2
from train_eval_pipeline import _build_env, _compute_action_dim, _validate_and_prepare_manifest


def analyze_test_data(manifest_path: str) -> Dict[str, Any]:
    """
    Analyze test dataset to understand state dimensions and case structure.
    """
    root = Path(__file__).resolve().parent.parent
    
    # Load and validate manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    prepared_manifest = _validate_and_prepare_manifest(manifest, root)
    test_files: List[str] = prepared_manifest["test_files"]
    
    print(f"📊 Analyzing {len(test_files)} test cases")
    print(f"{'='*70}\n")
    
    state_dims = {}
    analysis_results = []
    
    for idx, case in enumerate(test_files[:20], 1):  # ANALYZE FIRST 20
        case_path = str(root / case)
        
        try:
            env = _build_env(case_path)
            state_dim = env.state_dim
            action_dim = _compute_action_dim(env)
            
            if state_dim not in state_dims:
                state_dims[state_dim] = 0
            state_dims[state_dim] += 1
            
            analysis_results.append({
                "case": case.split("/")[-1],
                "state_dim": state_dim,
                "action_dim": action_dim,
                "total_classes": env.total_classes_to_schedule,
                "n_teachers": env.n_teachers,
                "n_groups": env.n_groups,
                "n_classrooms": env.n_classrooms,
                "n_timeslots": env.n_timeslots,
            })
            
            if idx % 5 == 0:
                print(f"[{idx}/20] Analyzed state_dim distributions so far: {state_dims}", flush=True)
        
        except Exception as e:
            print(f"[{idx}/20] ❌ Analysis failed for {case}: {e}", flush=True)
    
    return {
        "state_dim_distribution": state_dims,
        "distinct_state_dims": sorted(state_dims.keys()),
        "test_cases_analyzed": len(analysis_results),
        "sample_cases": analysis_results[:5],
    }


if __name__ == "__main__":
    manifest = "../data/dataset_compatible_1000/dataset_manifest.json"
    analysis = analyze_test_data(manifest)
    
    print(f"\n{'='*70}")
    print("📈 DATA STRUCTURE ANALYSIS")
    print(f"{'='*70}\n")
    print(json.dumps(analysis, indent=2, ensure_ascii=False))
