# TradePilot Dependency Graph (Mermaid)

Paste each diagram into **mermaid.live** to render.

---

## 1. System Flow (Top-Level)

```mermaid
flowchart TD
    subgraph DATA["DATA LAYER"]
        YF[yfinance]
        NSE[nsepython]
        RSS[Google News RSS]
        CSV[NSE CSV 2400+ files]
        CA[Cross-Asset DXY/BTC]
    end

    subgraph SIGNALS["SIGNAL LAYER (12 sources)"]
        ML[ML Engine 25%]
        RS[Relative Strength 20%]
        ORB[ORB Breakout 15%]
        VWAP[VWAP 10%]
        FII[FII/DII 10%]
        OI[Options OI 10%]
        VOL[Volume 10%]
        AH[Alpha Hunter NEW]
        XA[Cross-Asset NEW]
        MB[Market Breadth NEW]
        PCR[Options PCR NEW]
        CAL[Calendar Effects NEW]
    end

    subgraph DECISION["DECISION LAYER"]
        RD[Regime Detector]
        PM[Pre-Market Intel]
        SE[Signal Engine]
        CS[Composite Scorer]
    end

    subgraph RISK["RISK LAYER"]
        RM[Risk Manager 5-tier]
        POOL[Pool Manager 4 pools]
        PS[Position Sizer Kelly]
    end

    subgraph EXEC["EXECUTION (4 engines)"]
        V4[v4 Long-only]
        V5[v5 Long+Short+Alpha]
        V52[v5.2 F&O Options]
        V53[v5.3 Staged Entry]
    end

    subgraph OUTPUT["OUTPUT"]
        TG[Telegram Bot]
        WEB[Dashboard localhost:5050]
        PDF[PDF Reports]
        DB[DevPilot DB 79 learnings]
    end

    YF --> ML & RS & CS & AH
    NSE --> FII & OI & PCR
    RSS --> WEB
    CSV --> ML & MB
    CA --> XA

    ML & RS & ORB & VWAP & FII & OI & VOL --> CS
    AH & XA & MB & PCR & CAL --> DECISION

    CS --> SE
    RD --> SE & AH & V5 & V52 & V53
    PM --> RD
    SE --> RISK

    RM & POOL & PS --> EXEC

    V4 & V5 & V52 & V53 --> OUTPUT

    style V5 fill:#065f46,stroke:#22c55e,stroke-width:3px
    style RD fill:#dc2626,stroke:#ef4444,stroke-width:2px
    style CS fill:#4f46e5,stroke:#818cf8,stroke-width:2px
    style AH fill:#dc2626,stroke:#ef4444,stroke-width:2px
```

---

## 2. Module Dependencies (Detailed)

```mermaid
flowchart LR
    subgraph V4["V4 CORE"]
        CFG[config.py 225L]
        DN[data_nse.py 669L]
        MLE[ml_engine.py 803L]
        FI[features_intraday 405L]
        FINST[features_institutional 191L]
        COMP[composite_scorer 580L]
        PSIZ[position_sizer 288L]
    end

    subgraph V5["V5 MODULES"]
        RD[regime_detector 417L]
        PMI[premarket_intel 374L]
        SENG[signal_engine 259L]
        PMGR[pool_manager 337L]
        RMGR[risk_manager 595L]
        FFEED[fii_feed 371L]
        TBOT[telegram_bot 424L]
        CMPR[comparator 189L]
    end

    subgraph NEW["NEW SIGNALS"]
        AHUNT[alpha_hunter 672L]
        XASST[cross_asset 358L]
        MBRD[market_breadth 460L]
        OSIG[options_signals 438L]
        EFEAT[enhanced_features 289L]
    end

    subgraph SCRIPTS["SCRIPTS"]
        S4[v4-paper-trade 727L]
        S5[v5-paper-trade 692L]
        S52[v5.2-paper-trade 548L]
        S53[v5.3-paper-trade 1163L]
    end

    subgraph WEB["WEB"]
        APP[app.py 1851L]
    end

    CFG --> MLE & DN & COMP & SENG & MBRD & OSIG & PSIZ & EFEAT & APP
    DN --> COMP & RD
    MLE --> COMP
    FI --> COMP
    FINST --> COMP
    FFEED --> RD
    COMP --> SENG & S4 & APP
    RD --> SENG & AHUNT & S5 & S52 & S53 & CMPR
    SENG --> S5
    PMI --> CMPR
    AHUNT --> S5
    TBOT --> S5
    RMGR --> PMGR

    style CFG fill:#f59e0b,stroke:#fbbf24,stroke-width:3px
    style RD fill:#dc2626,stroke:#ef4444,stroke-width:3px
    style COMP fill:#4f46e5,stroke:#818cf8,stroke-width:3px
    style AHUNT fill:#dc2626,stroke:#ef4444,stroke-width:2px
    style S5 fill:#065f46,stroke:#22c55e,stroke-width:2px
```

---

## 3. Daily Trading Flow

```mermaid
flowchart TD
    A[08:30 AM Pre-Market] --> B[Pre-Market Intel]
    A --> C[Regime Detector]
    A --> D[Cross-Asset Scan]
    A --> E[Market Breadth]

    B --> F{Regime?}
    C --> F
    D --> F
    E --> F

    F -->|BULL| G[Deploy 100%]
    F -->|SIDEWAYS| H[Deploy 75%]
    F -->|BEAR| I[Deploy 30%]

    G --> J[09:35 Signal Engine]
    H --> J
    I --> J

    J --> K[Composite Score 201 stocks]
    K --> L[Top 20% = BUY]
    K --> M[Bottom 20% = SELL]

    L --> N[Risk Check]
    M --> N
    N --> O[Deploy to Pools]

    O --> P[10:00 AM Alpha Hunter]
    P --> Q{Sector Rotation?}
    Q -->|YES| R[Deploy 21% more into winners]
    Q -->|NO| S[Stay with current positions]

    R --> T[Monitor every 10 min]
    S --> T

    T --> U{SL/Target/Trailing?}
    U -->|SL Hit| V[Close + Telegram Alert]
    U -->|Target Hit| W[Close + Telegram Alert]
    U -->|Trailing| X[Adjust SL upward]
    U -->|Hold| T

    V --> Y[15:15 Force Close INTRADAY]
    W --> Y
    X --> T

    Y --> Z[Keep SWING positions overnight]
    Z --> AA[15:30 EOD Report]
    AA --> AB[Telegram Daily Summary]
    AA --> AC[Carry Forward Balance]
    AA --> AD[DevPilot DB Learnings]

    style P fill:#dc2626,stroke:#ef4444
    style F fill:#f59e0b,stroke:#fbbf24
    style N fill:#991b1b,stroke:#ef4444
```

---

## 4. Engine Comparison

```mermaid
graph LR
    subgraph V4["v4 — Control"]
        V4A[Long-only]
        V4B[No regime]
        V4C[Rs -19,279]
    end

    subgraph V5["v5 — Winner ★"]
        V5A[Long + Short]
        V5B[Regime-aware]
        V5C[Alpha Hunter]
        V5D[Rs +54,783]
    end

    subgraph V52["v5.2 — F&O"]
        V52A[4 Options strategies]
        V52B[Regime-driven]
        V52C[Rs -56,180]
    end

    subgraph V53["v5.3 — Staged"]
        V53A[3-tier conviction]
        V53B[Live price confirm]
        V53C[Rs 0]
    end

    MARKET[Same Market Same Capital Rs 10L] --> V4 & V5 & V52 & V53

    style V5 fill:#065f46,stroke:#22c55e,stroke-width:3px
    style V52 fill:#78350f,stroke:#f59e0b
    style V53 fill:#4a1d96,stroke:#8b5cf6
```

---

## How to Render

1. **Markmap** (for mind map): Go to [markmap.js.org/repl](https://markmap.js.org/repl), paste `tradepilot_markmap.md`
2. **Mermaid Live** (for dependency/flow): Go to [mermaid.live](https://mermaid.live), paste any mermaid block above
3. **VS Code**: Install "Markdown Preview Mermaid" extension, open this file
4. **Obsidian**: Native mermaid rendering, just open this file
5. **GitHub**: Renders mermaid blocks automatically in .md files
