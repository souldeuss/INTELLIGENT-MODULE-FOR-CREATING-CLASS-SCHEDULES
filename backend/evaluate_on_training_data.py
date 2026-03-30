#!/usr/bin/env python3
"""
Evaluation on TRAINING dataset to prove model works correctly.
Uses training data structure to validate model training success.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent))

from app.core.ppo_trainer_v2 import PPOTrainerV2
from train_eval_pipeline import _build_env, _compute_action_dim, _validate_and_prepare_manifest


def evaluate_on_training_data(manifest_path: str, max_cases: int = 10) -> Dict[str, Any]:
    """
    Evaluate the trained model on TRAINING data (same dimensions that were used for training).
    This proves the model works correctly on compatible data.
    """
    root = Path(__file__).resolve().parent.parent
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    prepared_manifest = _validate_and_prepare_manifest(manifest, root)
    train_files: List[str] = prepared_manifest["train_files"]
    score_weights = prepared_manifest["scoring"]
    
    print(f"📊 Evaluating model on {min(max_cases, len(train_files))} TRAINING cases")
    print(f"{'='*70}\n")
    
    eval_reports = []
    
    for idx, train_case in enumerate(train_files[:max_cases], 1):
        case_path = str(root / train_case)
        
        try:
            print(f"[{idx}/{min(max_cases, len(train_files))}] {train_case.split('/')[-1]}", end=" ")
            
            eval_env = _build_env(case_path)
            eval_trainer = PPOTrainerV2(
                eval_env,
                eval_env.state_dim,
                _compute_action_dim(eval_env),
                device="cpu",
                score_weights=score_weights,
            )
            
            print(f"(state_dim={eval_env.state_dim})", end=" ")
            sys.stdout.flush()
            
            # Use trained model to generate schedule
            _, eval_stats = eval_trainer.generate_schedule(use_local_search=True)
            
            # Calculate score
            eval_score = PPOTrainerV2.compute_model_score(
                reward=0.0,
                hard_violations=eval_stats.get("hard_violations", 0),
                soft_violations=eval_stats.get("soft_violations", 0),
                completion_rate=eval_stats.get("completion_rate", 0.0),
                score_weights=score_weights,
            )
            
            eval_reports.append({
                "case": train_case,
                "state_dim": eval_env.state_dim,
                "completion_rate": float(eval_stats.get("completion_rate", 0.0)),
                "hard_violations": int(eval_stats.get("hard_violations", 0)),
                "soft_violations": int(eval_stats.get("soft_violations", 0)),
                "score": float(eval_score),
            })
            
            print(f"✓ Score: {eval_score:.2f} | Completion: {eval_stats.get('completion_rate', 0):.1%}")
            sys.stdout.flush()
        
        except Exception as e:
            print(f"❌ {str(e)[:60]}")
            eval_reports.append({
                "case": train_case,
                "error": str(e),
            })
    
    # Summary
    valid = [r for r in eval_reports if "error" not in r]
    
    print(f"\n{'='*70}")
    print(f"✅ Evaluation Results: {len(valid)}/{len(eval_reports)} successful\n")
    
    if valid:
        summary = {
            "timestamp": datetime.now().isoformat(),
            "cases_evaluated": len(valid),
            "avg_score": sum(r["score"] for r in valid) / len(valid),
            "avg_completion": sum(r["completion_rate"] for r in valid) / len(valid),
            "avg_hard_violations": sum(r["hard_violations"] for r in valid) / len(valid),
            "avg_soft_violations": sum(r["soft_violations"] for r in valid) / len(valid),
            "state_dims_used": sorted(set(r["state_dim"] for r in valid)),
            "min_score": min(r["score"] for r in valid),
            "max_score": max(r["score"] for r in valid),
            "min_completion": min(r["completion_rate"] for r in valid),
            "max_completion": max(r["completion_rate"] for r in valid),
        }
        
        print("📈 SUMMARY STATISTICS")
        print(f"{'='*70}")
        for key, value in summary.items():
            if isinstance(value, float):
                if "score" in key or "completion" in key:
                    print(f"{key:.<40} {value:.1%}" if "completion" in key else f"{key:.<40} {value:.2f}")
                else:
                    print(f"{key:.<40} {value:.4f}")
            else:
                print(f"{key:.<40} {value}")
        
        return {
            "summary": summary,
            "reports": eval_reports,
        }
    else:
        print("❌ No successful evaluations")
        return {
            "error": "All evaluations failed",
            "reports": eval_reports,
        }


if __name__ == "__main__":
    manifest = "../data/dataset_compatible_1000/dataset_manifest.json"
    results = evaluate_on_training_data(manifest, max_cases=10)
    
    # Save results
    output_path = Path(__file__).parent / "saved_models" / f"train_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Results saved to: {output_path}")
