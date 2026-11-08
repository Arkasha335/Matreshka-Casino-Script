import os
import glob
import json
from datetime import datetime

LOG_DIR = r"D:\Vibe\matreshka-quantum\log storage"
OUTPUT_NORMALIZED = r"D:\Projects\MTCasinoScript\tools\audit\normalized_spins.json"
OUTPUT_REPORT = r"D:\Projects\MTCasinoScript\tools\audit\etl_report.json"

def run_etl():
    files = sorted(glob.glob(os.path.join(LOG_DIR, "*.json")))
    
    sessions = []
    total_raw_entries = 0
    parsing_issues = []
    
    all_normalized_spins = []
    
    for fpath in files:
        fname = os.path.basename(fpath)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            parsing_issues.append({"file": fname, "issue": f"JSON parse error: {e}"})
            continue

        meta = data.get("metadata", {})
        logs = data.get("logs", [])
        cycle_history = data.get("cycleHistory", None)
        
        session_id = fname.replace(".json", "")
        file_spins = len(logs)
        total_raw_entries += file_spins
        
        # Check timestamps consistency
        prev_ts = None
        session_anomalies = []
        normalized_session_spins = []
        
        for idx, entry in enumerate(logs):
            ts = entry.get("timestamp")
            outcome = entry.get("input_result")
            rec_action = entry.get("recommended_action")
            bet = entry.get("current_bet")
            step = entry.get("current_step")
            balance = entry.get("current_balance")
            server_state = entry.get("server_state_detected")
            time_since = entry.get("time_since_last_spin")
            mode = entry.get("current_mode") or entry.get("recovery_mode") or "UNKNOWN"
            
            # Validation
            entry_issues = []
            if outcome not in ["RED", "BLACK", "ZERO"]:
                entry_issues.append(f"Invalid outcome: {outcome}")
            if rec_action not in ["RED", "BLACK", "ZERO", None]:
                entry_issues.append(f"Invalid recommended_action: {rec_action}")
            if bet is None or bet < 0:
                entry_issues.append(f"Invalid bet: {bet}")
            if balance is None:
                entry_issues.append(f"Missing balance")
            if ts is None:
                entry_issues.append(f"Missing timestamp")
            elif prev_ts is not None and ts < prev_ts:
                entry_issues.append(f"Timestamp non-monotonic: {ts} < {prev_ts}")
            
            # Win/loss evaluation
            is_win = (outcome == rec_action and outcome != "ZERO")
            expected_payout = (bet * 0.98) if is_win else -bet
            
            spin_record = {
                "session_id": session_id,
                "spin_idx": idx,
                "timestamp": ts,
                "outcome": outcome,
                "recommended_action": rec_action,
                "bet": bet,
                "step": step,
                "balance": balance,
                "server_state": server_state,
                "time_since_last_spin_ms": time_since,
                "mode": mode,
                "is_win": is_win,
                "expected_delta": expected_payout,
                "has_issues": len(entry_issues) > 0,
                "issues": entry_issues
            }
            
            if entry_issues:
                session_anomalies.append({"spin_idx": idx, "issues": entry_issues})
                
            normalized_session_spins.append(spin_record)
            prev_ts = ts
            
        # Balance delta consistency check
        for i in range(len(normalized_session_spins) - 1):
            curr_s = normalized_session_spins[i]
            next_s = normalized_session_spins[i+1]
            actual_delta = next_s["balance"] - curr_s["balance"]
            curr_s["actual_next_balance_delta"] = actual_delta
            # Compare actual delta with curr_s expected delta
            diff = abs(actual_delta - curr_s["expected_delta"])
            curr_s["delta_matches_expected"] = diff < 1.0  # within 1 ruble due to rounding
        
        if normalized_session_spins:
            normalized_session_spins[-1]["actual_next_balance_delta"] = None
            normalized_session_spins[-1]["delta_matches_expected"] = None
            
        sessions.append({
            "session_id": session_id,
            "file": fname,
            "metadata": meta,
            "spins_count": file_spins,
            "has_cycle_history": cycle_history is not None,
            "anomalies_count": len(session_anomalies),
            "anomalies": session_anomalies
        })
        
        all_normalized_spins.extend(normalized_session_spins)
        
    report = {
        "total_files": len(files),
        "total_raw_entries": total_raw_entries,
        "total_normalized_spins": len(all_normalized_spins),
        "parsing_issues": parsing_issues,
        "sessions_summary": sessions
    }
    
    with open(OUTPUT_NORMALIZED, "w", encoding="utf-8") as f:
        json.dump(all_normalized_spins, f, indent=2, ensure_ascii=False)
        
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print(f"ETL completed successfully:")
    print(f"  Files processed: {len(files)}")
    print(f"  Total spins normalized: {len(all_normalized_spins)}")
    print(f"  Total parsing issues: {len(parsing_issues)}")
    total_anomalies = sum(s["anomalies_count"] for s in sessions)
    print(f"  Total spin-level anomalies: {total_anomalies}")
    print(f"  Exported to '{OUTPUT_NORMALIZED}' and '{OUTPUT_REPORT}'")

if __name__ == "__main__":
    run_etl()
