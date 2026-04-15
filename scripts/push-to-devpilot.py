#!/usr/bin/env python3
"""
Push TradePilot project data to DevPilot DB (dpxray).
Registers project, sprint, tasks, research, learnings, and documentation.

Usage:
    python3 scripts/push-to-devpilot.py
"""
import psycopg2
import json

DB_CONFIG = {
    "host": "localhost", "port": 5499,
    "user": "devpilot", "password": "TsUxQvfc7go5TDH8lsIKRTCv",
    "dbname": "devpilot",
}

PROJECT_ID = "tradepilot"
PROJECT_PATH = "/Users/soumyaswain/Documents/tinker/projects/tradepilot"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def push_project(cur):
    print("1. Registering project...")
    cur.execute("""
        INSERT INTO sdlc_projects (id, name, path, stage, status, tech_stack, metadata, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name, path = EXCLUDED.path,
            stage = EXCLUDED.stage, status = EXCLUDED.status,
            tech_stack = EXCLUDED.tech_stack, metadata = EXCLUDED.metadata,
            updated_at = NOW()
    """, (
        PROJECT_ID, "TradePilot", PROJECT_PATH,
        "development", "active",
        ["Python", "Flask", "XGBoost", "LightGBM", "yfinance", "Flutter", "Dart"],
        json.dumps({
            "description": "AI-powered Indian trading platform for beginner/Gen Z traders. "
                           "Ensemble ML with regime-aware scoring, paper trading, 2335 assets.",
            "day1_user": "Beginner traders (Gen Z, first-timers)",
            "revenue": "Freemium + Pro Rs 499-999/month",
            "regulatory": "AP under existing broker",
            "hook": "See your profit probability before every trade",
            "6mo_goal": "1000 paying users, product-market fit",
            "web_version": "v0.3",
            "flutter_version": "v0.1",
            "algorithm_version": "v3.0-regime-aware",
            "assets_count": 2335,
            "tabs": 11,
        }),
    ))
    print("   Done.")


def push_sprint(cur):
    print("2. Creating sprint...")
    cur.execute("""
        INSERT INTO sdlc_sprints (id, project_id, name, status, goal, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name, status = EXCLUDED.status,
            goal = EXCLUDED.goal, updated_at = NOW()
    """, (
        "TP-ALGO-V3-001", PROJECT_ID,
        "Algorithm v3 Rebuild -- Regime-Aware Precision Engine",
        "active",
        "Rebuild trading algorithm from 44.8% precision to 80% profitable trade ratio. "
        "Add market regime detection, relative strength vs NIFTY, P&L-weighted labels. "
        "Target: Sharpe > 2.0, 80% win rate on live trades.",
    ))
    print("   Done.")


def push_tasks(cur):
    print("3. Creating tasks...")
    tasks = [
        ("TP-ALGO-001", "Market regime detection (NIFTY 50 trend classifier)",
         "Classify market as BULL/BEAR/SIDEWAYS using NIFTY 50 SMA50/SMA200/ADX. "
         "Used for post-scoring threshold adjustment and position sizing.",
         "done", "high"),
        ("TP-ALGO-002", "Relative strength features (stock vs market alpha)",
         "Compute rs_5d and rs_20d: stock return minus NIFTY return.",
         "done", "high"),
        ("TP-ALGO-003", "P&L-weighted sample labels for training",
         "Multi-tier labels: STRONG_BUY(>3%), BUY(>1%), HOLD(-1 to 1%), AVOID(<-1%).",
         "done", "high"),
        ("TP-ALGO-004", "Train v3 ensemble and compare with v2",
         "XGBoost + LightGBM 500 trees. Result: 82.3% win rate, +214% return, 379 trades.",
         "done", "high"),
        ("TP-ALGO-005", "Wire v3 into Flask API with engine toggle",
         "Added ?engine=v3 to /api/scores, /api/model. New /api/compare endpoint.",
         "done", "medium"),
        ("TP-ALGO-006", "Post-scoring momentum + RS boost layer",
         "Two-layer scoring: ML base + momentum/RS boost + regime thresholds.",
         "done", "high"),
        ("TP-ALGO-007", "Validation framework: v2 vs v3 daily comparison",
         "Created v3-daily-compare.py. Day 1: v3 81.6% vs v2 79.6% accuracy.",
         "done", "medium"),
        ("TP-ALGO-008", "Precision tuning experiments (label configs)",
         "Tested CURRENT/HARDER/SHORTER. SHORTER hits 81.8% precision at threshold 0.68.",
         "done", "medium"),
        ("TP-ALGO-009", "Two-stage model: 3-day filter + 5-day sizer",
         "Use SHORTER high-precision classifier as gatekeeper. Target: 70%+ precision, 50+ trades.",
         "todo", "high"),
        ("TP-ALGO-010", "Run full week validation (Apr 7-11)",
         "Capture v2 and v3 predictions daily. Compare 5-day forward returns.",
         "in_progress", "high"),
        ("TP-ALGO-011", "Sector momentum features",
         "Add NIFTY Bank, IT, Pharma sector index returns as features.",
         "todo", "medium"),
        ("TP-ALGO-012", "Walk-forward cross-validation (rolling window)",
         "Replace single 80/20 split with expanding window CV.",
         "todo", "medium"),
    ]
    for task_id, title, desc, status, priority in tasks:
        cur.execute("""
            INSERT INTO sdlc_tasks (id, sprint_id, title, description, status, priority, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title, description = EXCLUDED.description,
                status = EXCLUDED.status, priority = EXCLUDED.priority, updated_at = NOW()
        """, (task_id, "TP-ALGO-V3-001", title, desc, status, priority))
    print(f"   {len(tasks)} tasks.")


def push_learnings(cur):
    print("4. Storing learnings...")
    learnings = [
        ("architecture", "Market features as training inputs collapse scores in bear markets",
         "When regime/mkt_return/mkt_volatility are direct ML features, they dominate (22-31% importance) "
         "and extrapolate to near-zero probability in extreme bear conditions. Fix: use market features "
         "ONLY for post-scoring threshold adjustment, not as training inputs. Relative strength "
         "(stock vs market) is the correct way to encode market context.",
         ["algorithm", "ml", "feature-engineering", "regime-detection"]),

        ("architecture", "Two-layer scoring beats single-model approach",
         "Stock-level ML model for base probability + post-scoring momentum/RS boost + regime-aware "
         "thresholds. ML handles long-term patterns; boost layer handles short-term momentum. "
         "Regime adjusts thresholds not features. Result: v3 81.6% vs v2 79.6% on day 1.",
         ["algorithm", "scoring", "ensemble"]),

        ("bug-pattern", "Precision-volume tradeoff: 80% precision kills trade count",
         "No single-label config achieved 70%+ precision with 20+ trades. SHORTER (>0.5% in 3d) "
         "hits 81.8% precision but only 11 trades. Solution: two-stage model where 3-day filter "
         "gates 5-day position sizer.",
         ["algorithm", "precision", "label-engineering"]),

        ("tool-pattern", "v3 HOLD precision 87.5% vs v2 66.7% on day 1",
         "v3 correctly upgraded INFY and MARUTI from AVOID to HOLD (both up 2.6-2.7%). "
         "Relative strength feature (rs_5d) correlates with intraday performance.",
         ["validation", "v3", "relative-strength"]),

        ("sprint-summary", "Algorithm v3 sprint: 8/12 tasks done in first session",
         "Built regime detector, relative strength, P&L-weighted labels, v3 ensemble (82.3% win rate), "
         "Flask API, validation framework, precision experiments. Key: market features must be "
         "post-scoring adjustments, not training inputs.",
         ["sprint", "algorithm", "v3"]),
    ]
    for category, title, content, tags in learnings:
        cur.execute("""
            INSERT INTO learnings (project, category, title, content, source, tags, active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'claude-code-session', %s, true, NOW(), NOW())
        """, (PROJECT_ID, category, title, content, tags))
    print(f"   {len(learnings)} learnings.")


def push_documentation(cur):
    print("5. Registering documentation...")
    docs = [
        ("tp-research", "Market Research & Competitive Analysis", "research",
         "Comprehensive analysis of Indian trading platform market, Zerodha/Groww/Angel One comparison"),
        ("tp-competitive", "Detailed Competitive Analysis", "research",
         "Feature-by-feature comparison of top 5 Indian brokers and trading platforms"),
        ("tp-product-brief", "Product Brief: MVP Features & User Flows", "planning",
         "Core feature set, user journey, tech stack decisions, scope boundaries"),
        ("tp-strategy-survey", "Strategy Survey: 12 Architectural Decisions", "planning",
         "Day-1 user, revenue model, regulatory path, AI approach, deployment strategy"),
        ("tp-sprint-plan", "8-Week MVP Sprint Plan", "planning",
         "4 sprints x 2 weeks: Foundation, Flutter UI, AI Scoring, Portfolio + Launch"),
        ("tp-pitch-deck", "Investor Pitch Deck", "pitch",
         "Problem, solution, market size, business model, traction, team, ask"),
        ("tp-session-0406", "Session Report: v0.3 Web + v0.1 Flutter", "report",
         "Apr 6 session: expanded to 451+ assets, 11 tabs, paper trading, Flutter app"),
        ("tp-validation-plan", "v2 vs v3 Validation Plan (Week Apr 7-11)", "validation",
         "Daily comparison framework, metrics to track, end-of-week analysis plan"),
    ]
    for code, title, category, summary in docs:
        cur.execute("""
            INSERT INTO documentation (code, title, content, category, project, summary, active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, true, NOW(), NOW())
            ON CONFLICT (code) DO UPDATE SET
                title = EXCLUDED.title, content = EXCLUDED.content,
                category = EXCLUDED.category, summary = EXCLUDED.summary, updated_at = NOW()
        """, (code, title, summary, category, PROJECT_ID, summary))
    print(f"   {len(docs)} documents.")


def push_research(cur):
    print("6. Storing research sources...")
    sources = [
        ("competitor", "Zerodha Kite Platform Analysis",
         "India's largest broker (15M+ users). Commission-free equity, Rs 20/F&O. "
         "No AI recommendations, no paper trading.", "https://zerodha.com"),
        ("competitor", "Groww Platform Analysis",
         "Fastest-growing (10M+ users). Clean beginner UI. TradePilot design inspired by Groww. "
         "Limited charting, no AI signals.", "https://groww.in"),
        ("market", "Indian Retail Trading Market Size 2026",
         "120M+ demat accounts. Active traders 5-10M/year. Gen Z fastest growing. "
         "TAM Rs 20,000 Cr. SAM Rs 2,000 Cr (AI platforms).", None),
        ("regulatory", "AP (Authorized Person) Regulatory Path",
         "AP under SEBI broker. Cost Rs 2-5L, 1-2 months. Requires NISM cert.", None),
    ]
    for i, (src_type, title, summary, url) in enumerate(sources, 1):
        src_id = f"tp-research-{i:03d}"
        cur.execute("""
            INSERT INTO research_sources (id, source_type, title, summary, url, project, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'completed', NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title, summary = EXCLUDED.summary, updated_at = NOW()
        """, (src_id, src_type, title, summary, url, PROJECT_ID))
    print(f"   {len(sources)} research sources.")


def push_survey(cur):
    print("7. Storing survey decisions...")
    decisions = [
        ("strategy", "target_user", "Who is the day-1 target user?",
         "Beginner traders (Gen Z, first-timers) -- 5-10M/year market"),
        ("strategy", "revenue_model", "What is the revenue model?",
         "Freemium + Pro subscription Rs 499-999/month"),
        ("strategy", "regulatory", "What regulatory path?",
         "Authorized Person (AP) under existing broker, 1-2 months, Rs 2-5L"),
        ("strategy", "core_hook", "What is the core product hook?",
         "See your profit probability before every trade -- AI trade scoring"),
        ("strategy", "6mo_goal", "What does success look like in 6 months?",
         "1,000 paying users, product-market fit proven"),
        ("product", "tech_stack", "What tech stack?",
         "Flutter mobile + Python Flask backend (migrating to Rust)"),
        ("product", "ai_approach", "What AI approach?",
         "XGBoost + LightGBM ensemble with regime-aware scoring (v3)"),
        ("product", "data_source", "Where does market data come from?",
         "yfinance (free), migrating to Zerodha WebSocket for live data"),
        ("product", "paper_trading", "Paper trading?",
         "Built-in paper trading terminal for risk-free practice"),
        ("product", "algo_target", "Algorithm performance target?",
         "80% profitable trade ratio, Sharpe > 2.0"),
        ("execution", "deployment", "Deployment strategy?",
         "Render.com for MVP, migrate to AWS/GCP for scale"),
        ("execution", "differentiation", "How to beat Zerodha/Groww?",
         "AI-first signals -- they are execution platforms, not intelligence platforms"),
    ]
    for i, (category, qid, question, answer) in enumerate(decisions, 1):
        survey_id = f"tp-survey-{i:03d}"
        cur.execute("""
            INSERT INTO idea_surveys (id, idea_id, round, question_id, question_text, selected_answer, category, active, created_at, updated_at)
            VALUES (%s, %s, 1, %s, %s, %s, %s, true, NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                selected_answer = EXCLUDED.selected_answer, updated_at = NOW()
        """, (survey_id, PROJECT_ID, qid, question, answer, category))
    print(f"   {len(decisions)} survey decisions.")


def main():
    print("=" * 60)
    print("  TradePilot -> DevPilot DB Push")
    print("=" * 60)
    try:
        conn = get_conn()
        conn.autocommit = False
        cur = conn.cursor()

        push_project(cur)
        push_sprint(cur)
        push_tasks(cur)
        push_learnings(cur)
        push_documentation(cur)
        push_research(cur)
        push_survey(cur)

        conn.commit()

        # Summary
        cur.execute("SELECT COUNT(*) FROM sdlc_tasks WHERE sprint_id = 'TP-ALGO-V3-001'")
        tasks = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM learnings WHERE project = 'tradepilot'")
        learns = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM documentation WHERE project = 'tradepilot'")
        docs = cur.fetchone()[0]

        print(f"\n{'='*60}")
        print(f"  ALL DATA PUSHED SUCCESSFULLY")
        print(f"{'='*60}")
        print(f"  Project:   tradepilot (registered)")
        print(f"  Sprint:    TP-ALGO-V3-001 (active)")
        print(f"  Tasks:     {tasks}")
        print(f"  Learnings: {learns}")
        print(f"  Docs:      {docs}")

        cur.close()
        conn.close()
    except psycopg2.OperationalError as e:
        print(f"\nERROR: Cannot connect to DevPilot DB at localhost:5499")
        print(f"Start Docker first, then: cd ~/Documents/tinker/devpilot/docker && docker compose up -d")


if __name__ == "__main__":
    main()
