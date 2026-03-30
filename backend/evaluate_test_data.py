#!/usr/bin/env python3
"""
Evaluation on TEST dataset - filtered by state_dim compatibility.
Tests model on test cases that match training state dimensions.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent))

from app.core.ppo_trainer_v2 import PPOTrainerV2
from train_eval_pipeline import _build_env, _compute_action_dim, _validate_and_prepare_manifest


def evaluate_compatible_test_cases(manifest_path: str, target_state_dim: int = None, max_cases: int = 20) -> Dict[str, Any]:
    """
    Evaluate trained model on test cases, filtering by state_dim if specified.
    This validates that test data processing works with compatible dimensions.
    """
    root = Path(__file__).resolve().parent.parent
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    prepared_manifest = _validate_and_prepare_manifest(manifest, root)
    test_files: List[str] = prepared_manifest["test_files"]
    score_weights = prepared_manifest["scoring"]
    
    print(f"📊 Testing on {len(test_files)} test cases")
    print(f"   Filtering by state_dim for compatibility...")
    print(f"{'='*70}\n")
    
    # First pass: identify available state dimensions
    state_dim_cases = {}
    compatible_test_files = []
    
    for test_case in test_files[:50]:  # Check first 50 to identify patterns
        case_path = str(root / test_case)
        try:
            env = _build_env(case_path)
            state_dim = env.state_dim
            if state_dim not in state_dim_cases:
                state_dim_cases[state_dim] = []
            state_dim_cases[state_dim].append(test_case)
        except:
            pass
    
    print(f"Found state_dim distribution in test set:")
    for dim in sorted(state_dim_cases.keys()):
        print(f"  state_dim={dim}: {len(state_dim_cases[dim])} cases")
    
    # Use most common state_dim if not specified
    if target_state_dim is None and state_dim_cases:
        target_state_dim = max(state_dim_cases.keys(), key=lambda k: len(state_dim_cases[k]))
        print(f"\n→ Using most common state_dim={target_state_dim} for evaluation")
    
    # Get test cases with target state_dim
    if target_state_dim in state_dim_cases:
        compatible_test_files = state_dim_cases[target_state_dim][:max_cases]
    else:
        print(f"❌ No test cases found with state_dim={target_state_dim}")
        return {"error": f"No compatible cases with state_dim={target_state_dim}"}
    
    print(f"   Evaluating {len(compatible_test_files)} compatible test cases\n")
    print(f"{'='*70}\n")
    
    eval_reports = []
    successful_count = 0
    
    for idx, test_case in enumerate(compatible_test_files, 1):
        case_name = test_case.split("/")[-1]
        case_path = str(root / test_case)
        
        try:
            print(f"[{idx}/{len(compatible_test_files)}] {case_name:30s}", end=" ", flush=True)
            
            eval_env = _build_env(case_path)
            eval_trainer = PPOTrainerV2(
                eval_env,
                eval_env.state_dim,
                _compute_action_dim(eval_env),
                device="cpu",
                score_weights=score_weights,
            )
            
            _, eval_stats = eval_trainer.generate_schedule(use_local_search=True)
            
            eval_score = PPOTrainerV2.compute_model_score(
                reward=0.0,
                hard_violations=eval_stats.get("hard_violations", 0),
                soft_violations=eval_stats.get("soft_violations", 0),
                completion_rate=eval_stats.get("completion_rate", 0.0),
                score_weights=score_weights,
            )
            
            eval_reports.append({
                "case": test_case,
                "state_dim": eval_env.state_dim,
                "completion_rate": float(eval_stats.get("completion_rate", 0.0)),
                "hard_violations": int(eval_stats.get("hard_violations", 0)),
                "soft_violations": int(eval_stats.get("soft_violations", 0)),
                "score": float(eval_score),
            })
            
            print(f"✓ Score={eval_score:6.2f} | Completion={eval_stats.get('completion_rate', 0):5.1%} | Hard={eval_stats.get('hard_violations', 0):2d}")
            successful_count += 1
            sys.stdout.flush()
        
        except Exception as e:
            print(f"❌ {str(e)[:40]}")
            eval_reports.append({
                "case": test_case,
                "error": str(e)[:100],
            })
    
    # Summary
    valid = [r for r in eval_reports if "error" not in r]
    
    print(f"\n{'='*70}")
    print(f"✅ TEST EVALUATION RESULTS: {successful_count}/{len(compatible_test_files)} successful\n")
    
    if valid:
        summary = {
            "timestamp": datetime.now().isoformat(),
            "test_cases_evaluated": len(valid),
            "total_test_cases_in_set": len(test_files),
            "compatible_state_dim": target_state_dim,
            "evaluation_success_rate": f"{successful_count}/{len(compatible_test_files)}",
            "avg_score": float(sum(r["score"] for r in valid) / len(valid)),
            "avg_completion_rate": float(sum(r["completion_rate"] for r in valid) / len(valid)),
            "avg_hard_violations": float(sum(r["hard_violations"] for r in valid) / len(valid)),
            "avg_soft_violations": float(sum(r["soft_violations"] for r in valid) / len(valid)),
            "min_score": float(min(r["score"] for r in valid)),
            "max_score": float(max(r["score"] for r in valid)),
            "min_completion": float(min(r["completion_rate"] for r in valid)),
            "max_completion": float(max(r["completion_rate"] for r in valid)),
        }
        
        print("📈 STATISTICS")
        print(f"{'='*70}")
        print(f"Test cases evaluated:         {summary['test_cases_evaluated']}/{len(test_files)}")
        print(f"Success rate:                 {summary['evaluation_success_rate']}")
        print(f"Average score:                {summary['avg_score']:.2f}")
        print(f"Average completion rate:      {summary['avg_completion_rate']:.1%}")
        print(f"Average hard violations:      {summary['avg_hard_violations']:.2f}")
        print(f"Average soft violations:      {summary['avg_soft_violations']:.2f}")
        print(f"Score range:                  {summary['min_score']:.2f} - {summary['max_score']:.2f}")
        print(f"Completion range:             {summary['min_completion']:.1%} - {summary['max_completion']:.1%}")
        
        return {
            "summary": summary,
            "reports": valid,
            "test_statistics_generated": True,
        }
    else:
        print("❌ No successful evaluations")
        return {
            "error": "All evaluations failed",
            "reports": eval_reports,
        }


if __name__ == "__main__":
    manifest = "../data/dataset_compatible_1000/dataset_manifest.json"
    results = evaluate_compatible_test_cases(manifest, target_state_dim=None, max_cases=20)
    
    # Save results
    output_dir = Path(__file__).parent / "saved_models"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"test_eval_compatible_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Results saved to: {output_path}")
