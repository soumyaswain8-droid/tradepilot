"""
TradePilot Stock Universe
=========================
Comprehensive Indian stock lists for NSE (.NS) and BSE (.BO) exchanges.

Coverage:
- NIFTY 50        : 50 large-cap stocks
- NIFTY Next 50   : 51-100 by market cap
- NIFTY 100       : Top 100 (NIFTY 50 + Next 50)
- NIFTY 200       : Top 200
- NIFTY 500       : Top 500 (covers ~94% of NSE market cap)
- BSE SENSEX 30   : Bombay Stock Exchange top 30
- BSE 200         : Top 200 BSE stocks (large + mid cap)
- BSE Sectoral    : Banks, IT, Defence, Infra, Power, Realty, Chemicals
- Sectoral indices: Bank, IT, Pharma, Auto, FMCG, Metal, Energy, Realty, Infra

Stats (as of 2026):
- NSE total listed: ~2,781 companies (~2,773 actively traded)
- BSE total listed: ~5,667 companies
- NIFTY 500 covers ~94% of total NSE free-float market cap

Data sources:
- NSE India index constituents: https://www.nseindia.com/
- niftystocks package: pip install niftystocks (auto-fetches latest constituents)
- Manual CSV: https://www.nseindia.com/market-data/securities-available-trading

Usage:
    from stock_universe import NIFTY_50, NIFTY_500, get_stocks_by_tier
    symbols = get_stocks_by_tier("nifty500")  # Returns list of "SYMBOL.NS" strings
"""

# ---------------------------------------------------------------------------
# NIFTY 50 (Large-cap, top 50 by free-float market cap)
# ---------------------------------------------------------------------------
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS",
    "ITC.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "HCLTECH.NS",
    "ASIANPAINT.NS", "SUNPHARMA.NS", "TITAN.NS", "WIPRO.NS", "ULTRACEMCO.NS",
    "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "M&M.NS", "TATAMOTORS.NS",
    "JSWSTEEL.NS", "TATASTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "TECHM.NS",
    "INDUSINDBK.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS", "SBILIFE.NS", "NESTLEIND.NS",
    "DRREDDY.NS", "DIVISLAB.NS", "CIPLA.NS", "COALINDIA.NS", "GRASIM.NS",
    "BRITANNIA.NS", "EICHERMOT.NS", "APOLLOHOSP.NS", "TATACONSUM.NS", "HEROMOTOCO.NS",
    "BAJAJ-AUTO.NS", "BPCL.NS", "UPL.NS", "HINDALCO.NS", "SHRIRAMFIN.NS",
]

# ---------------------------------------------------------------------------
# NIFTY NEXT 50 (Stocks ranked 51-100 by market cap)
# ---------------------------------------------------------------------------
NIFTY_NEXT_50 = [
    "ADANIGREEN.NS", "ADANIPOWER.NS", "AMBUJACEM.NS", "ATGL.NS", "AWL.NS",
    "BANKBARODA.NS", "BEL.NS", "BERGEPAINT.NS", "BOSCHLTD.NS", "CANBK.NS",
    "CHOLAFIN.NS", "COLPAL.NS", "CONCOR.NS", "DLF.NS", "DABUR.NS",
    "DMART.NS", "GAIL.NS", "GODREJCP.NS", "HAVELLS.NS", "HAL.NS",
    "ICICIPRULI.NS", "ICICIGI.NS", "IDEA.NS", "INDHOTEL.NS", "INDIGO.NS",
    "IOC.NS", "IRCTC.NS", "IRFC.NS", "JINDALSTEL.NS", "JIOFIN.NS",
    "LICI.NS", "LTIM.NS", "LTTS.NS", "LUPIN.NS", "MARICO.NS",
    "MAXHEALTH.NS", "MCDOWELL-N.NS", "MOTHERSON.NS", "MUTHOOTFIN.NS", "NAUKRI.NS",
    "NHPC.NS", "PERSISTENT.NS", "PIDILITIND.NS", "PFC.NS", "PNB.NS",
    "RECLTD.NS", "SIEMENS.NS", "SRF.NS", "TATAPOWER.NS", "TORNTPHARM.NS",
]

# ---------------------------------------------------------------------------
# NIFTY 200 additional stocks (101-200, mid-cap leaders)
# ---------------------------------------------------------------------------
NIFTY_200_EXTRA = [
    "ABB.NS", "ABCAPITAL.NS", "ABFRL.NS", "ACC.NS", "AJANTPHARM.NS",
    "ALKEM.NS", "APLLTD.NS", "ASHOKLEY.NS", "ASTRAL.NS", "AUROPHARMA.NS",
    "BALKRISIND.NS", "BANDHANBNK.NS", "BATAINDIA.NS", "BHEL.NS", "BIOCON.NS",
    "BSE.NS", "CANFINHOME.NS", "CGPOWER.NS", "COFORGE.NS", "CROMPTON.NS",
    "CUMMINSIND.NS", "DEEPAKNTR.NS", "DELHIVERY.NS", "DEVYANI.NS", "DIXON.NS",
    "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS", "FORTIS.NS", "GICRE.NS",
    "GLAND.NS", "GMRINFRA.NS", "GODREJPROP.NS", "GSPL.NS", "HDFCAMC.NS",
    "HINDPETRO.NS", "HONAUT.NS", "IDFCFIRSTB.NS", "IEX.NS", "INDIANB.NS",
    "INDUSTOWER.NS", "IREDA.NS", "JKCEMENT.NS", "JSL.NS", "JUBLFOOD.NS",
    "KALYANKJIL.NS", "KEI.NS", "KPITTECH.NS", "L&TFH.NS", "LAURUSLABS.NS",
    "LICHSGFIN.NS", "LODHA.NS", "LTF.NS", "M&MFIN.NS", "MANAPPURAM.NS",
    "MANKIND.NS", "MFSL.NS", "MGL.NS", "MPHASIS.NS", "MRF.NS",
    "NIACL.NS", "NMDC.NS", "OBEROIRLTY.NS", "OFSS.NS", "OIL.NS",
    "PAGEIND.NS", "PATANJALI.NS", "PETRONET.NS", "POLYCAB.NS", "PRESTIGE.NS",
    "PVRINOX.NS", "RAMCOCEM.NS", "SAIL.NS", "SBICARD.NS", "SCHAEFFLER.NS",
    "SHREECEM.NS", "SJVN.NS", "SONACOMS.NS", "SUNDARMFIN.NS", "SUNTV.NS",
    "SUPREMEIND.NS", "SYNGENE.NS", "TATACHEM.NS", "TATACOMM.NS", "TATAELXSI.NS",
    "TATATECH.NS", "THERMAX.NS", "TIINDIA.NS", "TORNTPOWER.NS", "TRENT.NS",
    "TVSMOTOR.NS", "UNIONBANK.NS", "UNITDSPR.NS", "VOLTAS.NS", "YESBANK.NS",
    "ZOMATO.NS", "ZYDUSLIFE.NS", "PAYTM.NS", "NYKAA.NS", "POLICYBZR.NS",
]

# ---------------------------------------------------------------------------
# NIFTY 500 additional stocks (201-500, mid-cap and small-cap)
# These cover the remaining ~94% of NSE market cap
# ---------------------------------------------------------------------------
NIFTY_500_EXTRA = [
    # Financials
    "AAVAS.NS", "ABSLAMC.NS", "AUBANK.NS", "BAJAJHLDNG.NS", "CENTRALBK.NS",
    "CREDITACC.NS", "CSBBANK.NS", "EQUITASBNK.NS", "FINCABLES.NS", "GRINDWELL.NS",
    "IIFL.NS", "IIFLWAM.NS", "JMFINANCIL.NS", "KARURVYSYA.NS", "KFINTECH.NS",
    "KOTAKBANK.NS", "MAHABANK.NS", "MOTILALOFS.NS", "NAM-INDIA.NS", "POONAWALLA.NS",
    "RBLBANK.NS", "SBFC.NS", "SUNDARMHLD.NS", "UCOBANK.NS", "UTIAMC.NS",
    # IT & Tech
    "BSOFT.NS", "CYIENT.NS", "ECLERX.NS", "HAPPSTMNDS.NS", "INTELLECT.NS",
    "LATENTVIEW.NS", "MASTEK.NS", "NEWGEN.NS", "NIITLTD.NS", "OFSS.NS",
    "ROUTE.NS", "RVNL.NS", "TANLA.NS", "TTML.NS", "ZENSAR.NS",
    # Pharma & Healthcare
    "AARTIDRUGS.NS", "AARTIIND.NS", "APOLLOTYRE.NS", "ASTRAZEN.NS", "ATUL.NS",
    "BIRLACORP.NS", "CADILAHC.NS", "ERIS.NS", "GLENMARK.NS", "GRANULES.NS",
    "IPCALAB.NS", "JBCHEPHARM.NS", "JUBLPHARMA.NS", "KAMEDICA.NS", "LALPATHLAB.NS",
    "NATCOPHARM.NS", "RAINBOW.NS", "STAR.NS", "SUPRIYA.NS", "SUVENPHAR.NS",
    "TORNTPHARM.NS", "ZYDUSWELL.NS",
    # Auto & Auto Ancillaries
    "AMARAJABAT.NS", "APLAPOLLO.NS", "BHARATFORG.NS", "CEATLTD.NS", "CRAFTSMAN.NS",
    "ENDURANCE.NS", "EXIDEIND.NS", "FIVESTAR.NS", "GABRIEL.NS", "GREENPANEL.NS",
    "JBMA.NS", "KIRLOSENG.NS", "MAHINDCIE.NS", "MINDA.NS", "MOTHERSON.NS",
    "MSUMI.NS", "MRF.NS", "RELAXO.NS", "SCHAEFFLER.NS", "SKFINDIA.NS",
    "SONACOMS.NS", "SUBROS.NS", "SUNDRMFAST.NS", "SUPRAJIT.NS", "TIMKEN.NS",
    "TVSMOTOR.NS", "VARROC.NS", "WHEELS.NS",
    # Consumer & FMCG
    "ALOKINDS.NS", "BIKAJI.NS", "BALRAMCHIN.NS", "BBTC.NS", "CCL.NS",
    "COLPAL.NS", "DEVYANI.NS", "EMAMILTD.NS", "GODFRYPHLP.NS", "GODREJIND.NS",
    "HATSUN.NS", "JYOTHYLAB.NS", "KRBL.NS", "MARICO.NS", "METROBRAND.NS",
    "RADICO.NS", "RAJESHEXPO.NS", "SAPPHIRE.NS", "TATACONSUM.NS", "VENKEYS.NS",
    "VBL.NS", "VSTIND.NS", "ZENSARTECH.NS",
    # Metals & Mining
    "APLAPOLLO.NS", "HINDZINC.NS", "JSWENERGY.NS", "JSWINFRA.NS", "JSL.NS",
    "MOIL.NS", "NALCO.NS", "NATIONALUM.NS", "NMDC.NS", "RATNAMANI.NS",
    "SAIL.NS", "VEDL.NS", "WELCORP.NS",
    # Cement & Building Materials
    "AMBUJACEM.NS", "BIRLASOFT.NS", "DALBHARAT.NS", "HEIDELBERG.NS", "INDIACEM.NS",
    "JKCEMENT.NS", "JKLAKSHMI.NS", "NUVOCO.NS", "ORIENTCEM.NS", "PRISMJOINS.NS",
    "RAMCOCEM.NS", "SHREECEM.NS", "STARCEMENT.NS", "ULTRACEMCO.NS",
    # Energy & Power
    "ADANIENSOL.NS", "ADANIGREEN.NS", "CESC.NS", "GIPCL.NS", "GPPL.NS",
    "GUJGASLTD.NS", "IGL.NS", "IREDA.NS", "JSWENERGY.NS", "JSPL.NS",
    "MGL.NS", "NHPC.NS", "NTPC.NS", "POWERGRID.NS", "PTC.NS",
    "RECLTD.NS", "SJVN.NS", "TATAPOWER.NS", "TORNTPOWER.NS",
    # Capital Goods & Infrastructure
    "ABB.NS", "BEL.NS", "BHEL.NS", "BLS.NS", "BRIGADE.NS",
    "CGPOWER.NS", "COCHINSHIP.NS", "CUMMINSIND.NS", "DEEPAKFERT.NS", "ELGIEQUIP.NS",
    "EMUDHRA.NS", "ENGINERSIN.NS", "FACT.NS", "GRSE.NS", "HCC.NS",
    "IBREALEST.NS", "IRCON.NS", "IRB.NS", "JKIL.NS", "KALPATPOWR.NS",
    "KIRLOSENG.NS", "KEC.NS", "MAZAGON.NS", "NCC.NS", "NBCC.NS",
    "PGEL.NS", "RITES.NS", "RVNL.NS", "SADBHAV.NS", "SUZLON.NS",
    "THERMAX.NS", "TITAGARH.NS", "TRIVENI.NS", "VOLTAS.NS",
    # Chemicals
    "AARTI.NS", "ATUL.NS", "CASTROLIND.NS", "CLEAN.NS", "DEEPAKNTR.NS",
    "FINEORG.NS", "FLUOROCHEM.NS", "GALAXYSURF.NS", "GNFC.NS", "GSFC.NS",
    "GUJALKALI.NS", "LXCHEM.NS", "NAVINFLUOR.NS", "NOCIL.NS", "PIDILITIND.NS",
    "PI.NS", "ROSSARI.NS", "SRF.NS", "SUMICHEM.NS", "TATACHEM.NS",
    "UPL.NS", "VINATIORG.NS",
    # Telecom & Media
    "BHARTIARTL.NS", "IDEA.NS", "TTML.NS", "HATHWAY.NS", "NAZARA.NS",
    "SUNTV.NS", "TATACOMM.NS", "ZEEL.NS",
    # Textiles & Apparel
    "ARVIND.NS", "GOKEX.NS", "KITEX.NS", "PAGEIND.NS", "RAYMOND.NS",
    "TRENT.NS", "VEDANTFASH.NS",
    # Real Estate
    "BRIGADE.NS", "DLF.NS", "GODREJPROP.NS", "LODHA.NS", "OBEROIRLTY.NS",
    "PHOENIXLTD.NS", "PRESTIGE.NS", "SOBHA.NS", "SUNTECK.NS",
    # Logistics & Transport
    "BLUEDART.NS", "CONCOR.NS", "DELHIVERY.NS", "INDIGO.NS", "IRCTC.NS",
    "SPICEJET.NS", "TCI.NS", "TIINDIA.NS", "VRL.NS",
    # Miscellaneous
    "3MINDIA.NS", "AFFLE.NS", "CAMPUS.NS", "CARTRADE.NS", "EASEMYTRIP.NS",
    "HONAUT.NS", "INDIAMART.NS", "INDIGOPNTS.NS", "KAYNES.NS", "LTFOODS.NS",
    "MAHLIFE.NS", "MAPMYINDIA.NS", "MATRIMONY.NS", "MCX.NS", "NAVNETEDUL.NS",
    "NH.NS", "OLECTRA.NS", "PGHH.NS", "QUESS.NS", "REDINGTON.NS",
    "SOLARINDS.NS", "SWIGGY.NS", "TATAINVEST.NS", "VAIBHAVGBL.NS", "ZOMATO.NS",
]

# ---------------------------------------------------------------------------
# BSE SENSEX 30
# ---------------------------------------------------------------------------
BSE_SENSEX_30 = [
    "RELIANCE.BO", "TCS.BO", "HDFCBANK.BO", "INFY.BO", "ICICIBANK.BO",
    "HINDUNILVR.BO", "SBIN.BO", "BHARTIARTL.BO", "KOTAKBANK.BO", "LT.BO",
    "ITC.BO", "AXISBANK.BO", "BAJFINANCE.BO", "MARUTI.BO", "HCLTECH.BO",
    "ASIANPAINT.BO", "SUNPHARMA.BO", "TITAN.BO", "WIPRO.BO", "ULTRACEMCO.BO",
    "M&M.BO", "NTPC.BO", "POWERGRID.BO", "TATAMOTORS.BO", "NESTLEIND.BO",
    "TATASTEEL.BO", "INDUSINDBK.BO", "TECHM.BO", "BAJAJFINSV.BO", "ADANIENT.BO",
]

# ---------------------------------------------------------------------------
# BSE 200 (top large/mid caps by market cap — .BO suffix)
# ---------------------------------------------------------------------------
BSE_200 = [
    # Sensex 30 overlap (large caps)
    "RELIANCE.BO", "TCS.BO", "HDFCBANK.BO", "INFY.BO", "ICICIBANK.BO",
    "HINDUNILVR.BO", "SBIN.BO", "BHARTIARTL.BO", "LT.BO", "ITC.BO",
    "AXISBANK.BO", "BAJFINANCE.BO", "KOTAKBANK.BO", "MARUTI.BO", "HCLTECH.BO",
    "ASIANPAINT.BO", "SUNPHARMA.BO", "TITAN.BO", "WIPRO.BO", "ULTRACEMCO.BO",
    "M&M.BO", "NTPC.BO", "POWERGRID.BO", "TATAMOTORS.BO", "NESTLEIND.BO",
    "TATASTEEL.BO", "ADANIENT.BO", "TECHM.BO", "BAJAJFINSV.BO", "INDUSINDBK.BO",
    # Adani group
    "ADANIPORTS.BO", "ADANIPOWER.BO", "ADANIGREEN.BO", "ADANIENSOL.BO", "ATGL.BO", "AWL.BO",
    # Banks (public + private)
    "BANKBARODA.BO", "CANBK.BO", "MAHABANK.BO", "INDIANB.BO", "CENTRALBK.BO",
    "UCOBANK.BO", "BANKINDIA.BO", "UNIONBANK.BO", "PSB.BO", "J&KBANK.BO",
    # Defence & shipbuilding
    "GRSE.BO", "BDL.BO", "BEML.BO", "MAZDOCK.BO", "COCHINSHIP.BO",
    # Infrastructure & metals
    "JSWENERGY.BO", "JINDALSTEL.BO", "LLOYDSME.BO", "IRCON.BO", "RVNL.BO",
    "NBCC.BO", "NCC.BO", "HCC.BO", "WELCORP.BO",
    # Media
    "NDTV.BO",
    # FMCG & consumer
    "PGHL.BO", "VENKEYS.BO", "RELAXO.BO", "VBL.BO", "ZYDUSWELL.BO",
    # IT & tech (mid-cap)
    "HAPPSTMNDS.BO", "NEWGEN.BO", "MASTEK.BO", "CYIENT.BO",
    # Pharma
    "SUVEN.BO", "WINDLAS.BO",
    # Financial services
    "MOTILALOFS.BO", "ANGEL.BO", "IIFL.BO", "PAISALO.BO", "M&MFIN.BO", "NSDL.BO",
    # Power & utilities
    "TATAPOWER.BO", "CESC.BO", "TORNTPOWER.BO", "NHPC.BO", "SJVN.BO",
    # Real estate
    "SOBHA.BO", "BRIGADE.BO", "KOLTEPATIL.BO",
    # TV & media
    "SUNTV.BO",
    # Auto & engineering
    "FORCEMOT.BO", "ESCORTS.BO", "TIINDIA.BO",
    # Chemicals
    "DEEPAKNTR.BO", "NAVINFLUOR.BO", "ATUL.BO", "CLEAN.BO",
    # Specialty
    "ARE&M.BO", "GVTD.BO",
]

# ---------------------------------------------------------------------------
# BSE Sectoral Lists
# ---------------------------------------------------------------------------
BSE_BANKS = [
    "SBIN.BO", "HDFCBANK.BO", "ICICIBANK.BO", "AXISBANK.BO", "KOTAKBANK.BO",
    "BANKBARODA.BO", "CANBK.BO", "MAHABANK.BO", "INDIANB.BO", "CENTRALBK.BO",
    "UCOBANK.BO", "BANKINDIA.BO", "UNIONBANK.BO", "PSB.BO", "INDUSINDBK.BO",
    "J&KBANK.BO",
]

BSE_IT = [
    "TCS.BO", "INFY.BO", "HCLTECH.BO", "WIPRO.BO", "TECHM.BO",
    "HAPPSTMNDS.BO", "NEWGEN.BO", "MASTEK.BO", "CYIENT.BO",
]

BSE_DEFENCE = [
    "BDL.BO", "BEML.BO", "GRSE.BO", "MAZDOCK.BO", "COCHINSHIP.BO",
]

BSE_INFRA = [
    "LT.BO", "ADANIENT.BO", "ADANIPORTS.BO", "IRCON.BO", "RVNL.BO",
    "NBCC.BO", "NCC.BO", "HCC.BO", "JSWENERGY.BO", "JINDALSTEL.BO",
]

BSE_POWER = [
    "NTPC.BO", "POWERGRID.BO", "TATAPOWER.BO", "CESC.BO", "TORNTPOWER.BO",
    "NHPC.BO", "SJVN.BO", "ADANIGREEN.BO", "ADANIENSOL.BO", "JSWENERGY.BO",
]

BSE_REALTY = [
    "SOBHA.BO", "BRIGADE.BO", "KOLTEPATIL.BO",
]

BSE_CHEMICALS = [
    "DEEPAKNTR.BO", "NAVINFLUOR.BO", "ATUL.BO", "CLEAN.BO",
]

# ---------------------------------------------------------------------------
# Sectoral Indices (NSE)
# ---------------------------------------------------------------------------
NIFTY_BANK = [
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS",
    "INDUSINDBK.NS", "BANKBARODA.NS", "PNB.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS",
    "BANDHANBNK.NS", "AUBANK.NS",
]

NIFTY_IT = [
    "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS",
    "LTIM.NS", "LTTS.NS", "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS",
]

NIFTY_PHARMA = [
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "LUPIN.NS",
    "AUROPHARMA.NS", "TORNTPHARM.NS", "BIOCON.NS", "ALKEM.NS", "GLENMARK.NS",
]

NIFTY_AUTO = [
    "TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS",
    "HEROMOTOCO.NS", "TVSMOTOR.NS", "ASHOKLEY.NS", "BHARATFORG.NS", "MRF.NS",
    "BALKRISIND.NS", "MOTHERSON.NS", "BOSCHLTD.NS", "EXIDEIND.NS", "APOLLOTYRE.NS",
]

NIFTY_FMCG = [
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS",
    "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "COLPAL.NS", "VBL.NS",
    "EMAMILTD.NS", "RADICO.NS", "JYOTHYLAB.NS", "BIKAJI.NS", "VSTIND.NS",
]

NIFTY_METAL = [
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "COALINDIA.NS",
    "NMDC.NS", "SAIL.NS", "JINDALSTEL.NS", "NATIONALUM.NS", "HINDZINC.NS",
    "APLAPOLLO.NS", "RATNAMANI.NS", "MOIL.NS", "NALCO.NS", "WELCORP.NS",
]

NIFTY_ENERGY = [
    "RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "BPCL.NS",
    "COALINDIA.NS", "IOC.NS", "GAIL.NS", "ADANIGREEN.NS", "TATAPOWER.NS",
    "ADANIENT.NS", "HINDPETRO.NS", "PETRONET.NS", "IGL.NS", "OIL.NS",
]

NIFTY_REALTY = [
    "DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "LODHA.NS",
    "PHOENIXLTD.NS", "BRIGADE.NS", "SOBHA.NS", "SUNTECK.NS", "IBREALEST.NS",
]

NIFTY_INFRA = [
    "LT.NS", "ADANIENT.NS", "ADANIPORTS.NS", "ULTRACEMCO.NS", "GRASIM.NS",
    "NTPC.NS", "POWERGRID.NS", "DLF.NS", "BHARTIARTL.NS", "TATAPOWER.NS",
    "SIEMENS.NS", "ABB.NS", "HAVELLS.NS", "CONCOR.NS", "IRB.NS",
]

# ---------------------------------------------------------------------------
# NSE ETFs (Exchange Traded Funds — track indices, gold, bonds)
# ---------------------------------------------------------------------------
NSE_ETFS = [
    # Equity / Index ETFs
    "NIFTYBEES.NS", "BANKBEES.NS", "JUNIORBEES.NS", "SETFNIFTY.NS",
    "SETFNIF50.NS", "MON100.NS", "SETFNN50.NS",
    # Sectoral ETFs
    "SETFNIFBK.NS", "ITBEES.NS", "PHARMABEES.NS", "INFRABEES.NS",
    "PSUBNKBEES.NS", "CONSUMBEES.NS", "DIVOPPBEES.NS",
    "HABORETF.NS", "HEALTHIETF.NS", "DEFENCEETF.NS",
    # Midcap / Smallcap ETFs
    "MOM100.NS", "MIDSELIETF.NS", "MIDCAPIETF.NS",
    # Gold ETFs
    "GOLDBEES.NS", "GOLDCASE.NS", "GOLD1.NS", "GOLDIETF.NS",
    # Silver ETFs
    "SILVERBEES.NS", "SILVERIETF.NS",
    # Commodity ETFs
    "CPSEETF.NS",
    # International ETFs
    "MAFANG.NS", "N100.NS", "USIGETF.NS",
    # Debt / Liquid ETFs
    "LIQUIDBEES.NS", "LIQUIDCASE.NS", "LIQUIDADD.NS",
    "NETFGILT5Y.NS", "NETFSDL26.NS",
    # Thematic ETFs
    "MOMENTUM.NS", "LOWVOLIETF.NS", "ALPHAETF.NS", "EQUAL50.NS",
    "BHARAT22.NS", "SENSEXETF.NS",
]

# ETF Categories (for Groww-style ETF sub-tabs)
ETF_CATEGORIES = {
    "equity": ["NIFTYBEES.NS", "BANKBEES.NS", "JUNIORBEES.NS", "SETFNIFTY.NS", "SETFNIF50.NS"],
    "index": ["NIFTYBEES.NS", "BANKBEES.NS", "JUNIORBEES.NS", "MON100.NS", "SENSEXETF.NS"],
    "gold": ["GOLDBEES.NS", "GOLDCASE.NS", "GOLD1.NS", "GOLDIETF.NS"],
    "silver": ["SILVERBEES.NS", "SILVERIETF.NS"],
    "commodity": ["GOLDBEES.NS", "SILVERBEES.NS", "CPSEETF.NS"],
    "debt": ["LIQUIDBEES.NS", "LIQUIDCASE.NS", "LIQUIDADD.NS", "NETFGILT5Y.NS"],
    "international": ["MAFANG.NS", "N100.NS", "USIGETF.NS"],
    "sectoral": ["ITBEES.NS", "PHARMABEES.NS", "INFRABEES.NS", "PSUBNKBEES.NS", "CONSUMBEES.NS"],
    "midcap": ["MOM100.NS", "MIDSELIETF.NS", "MIDCAPIETF.NS"],
    "defence": ["DEFENCEETF.NS"],
    "healthcare": ["HEALTHIETF.NS"],
    "liquid": ["LIQUIDBEES.NS", "LIQUIDCASE.NS", "LIQUIDADD.NS"],
}

# ---------------------------------------------------------------------------
# Market Indices (for tracking, not scoring)
# ---------------------------------------------------------------------------
MARKET_INDICES = {
    # NSE Broad Market
    "NIFTY 50": "^NSEI",
    "NIFTY Next 50": "^NSEI",  # tracked via constituent stocks
    "NIFTY 100": "^CNX100",
    "NIFTY 200": "^CNX200",
    "NIFTY 500": "^CNX500",
    "NIFTY Midcap 100": "^CNXMIDCAP",
    "NIFTY Midcap 150": "NIFTYMIDCAP150.NS",
    "NIFTY Smallcap 100": "^CNXSMALLCAP",
    "India VIX": "^INDIAVIX",
    # NSE Sectoral
    "NIFTY Bank": "^NSEBANK",
    "NIFTY IT": "^CNXIT",
    "NIFTY Pharma": "^CNXPHARMA",
    "NIFTY Auto": "^CNXAUTO",
    "NIFTY Metal": "^CNXMETAL",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY Energy": "^CNXENERGY",
    "NIFTY Realty": "^CNXREALTY",
    "NIFTY Infra": "^CNXINFRA",
    "NIFTY PSU Bank": "^CNXPSUBANK",
    "NIFTY Fin Service": "NIFTY_FIN_SERVICE.NS",
    "NIFTY Pvt Bank": "NIFTYPVTBANK.NS",
    "NIFTY Healthcare": "NIFTY_HEALTHCARE.NS",
    "NIFTY Consumer": "NIFTY_CONSUMPTION.NS",
    "NIFTY Media": "^CNXMEDIA",
    "NIFTY Defence": "NIFTY_DEF.NS",
    # BSE
    "BSE SENSEX": "^BSESN",
    "BSE 100": "BSE-100.BO",
    "BSE BANKEX": "BSE-BANK.BO",
    "BSE Midcap": "BSE-MIDCAP.BO",
    "BSE Smallcap": "BSE-SMLCAP.BO",
    # Global Indices
    "S&P 500": "^GSPC",
    "Dow Jones": "^DJI",
    "NASDAQ": "^IXIC",
    "FTSE 100": "^FTSE",
    "Nikkei 225": "^N225",
    "Hang Seng": "^HSI",
    "KOSPI": "^KS11",
    "DAX": "^GDAXI",
    "CAC 40": "^FCHI",
    "Shanghai": "000001.SS",
    # Futures
    "Dow Jones Futures": "YM=F",
    "S&P 500 Futures": "ES=F",
    "NASDAQ Futures": "NQ=F",
}

# ---------------------------------------------------------------------------
# Commodities (Global + MCX proxies via yfinance)
# ---------------------------------------------------------------------------
COMMODITIES = {
    # Precious Metals
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Platinum": "PL=F",
    # Energy
    "Crude Oil (WTI)": "CL=F",
    "Crude Oil (Brent)": "BZ=F",
    "Natural Gas": "NG=F",
    # Agriculture
    "Cotton": "CT=F",
    "Sugar": "SB=F",
    "Wheat": "ZW=F",
    "Corn": "ZC=F",
    "Soybean": "ZS=F",
    # Metals
    "Copper": "HG=F",
    "Aluminium": "ALI=F",
    "Zinc": "ZN=F",
    "Nickel": "NI=F",
    # MCX proxies (Indian commodity-linked stocks)
    "MCX (exchange)": "MCX.NS",
    "ONGC (crude proxy)": "ONGC.NS",
    "Hindalco (aluminium)": "HINDALCO.NS",
    "Vedanta (metals)": "VEDL.NS",
    "NMDC (iron ore)": "NMDC.NS",
    "Coal India (coal)": "COALINDIA.NS",
}

# ---------------------------------------------------------------------------
# Mutual Fund Proxies (AMC stocks + popular MF ETFs)
# AMC stocks move with AUM growth — proxy for MF industry health
# ---------------------------------------------------------------------------
MF_PROXIES = [
    # AMC stocks (Asset Management Companies)
    "HDFCAMC.NS",     # HDFC AMC — India's largest AMC
    "NAM-INDIA.NS",   # Nippon India AMC
    "UTIAMC.NS",      # UTI AMC
    "ABSLAMC.NS",     # Aditya Birla Sun Life AMC
    # Wealth managers & distributors
    "MOTILALOFS.NS",  # Motilal Oswal Financial
    "IIFLWAM.NS",     # IIFL Wealth Management
    "KFINTECH.NS",    # KFin Technologies (MF registrar)
    # Popular Index Fund ETFs (track MF performance)
    "NIFTYBEES.NS",   # Nifty 50 Index Fund proxy
    "JUNIORBEES.NS",  # Nifty Next 50 proxy
    "MIDCPBEES.NS",   # Midcap Index Fund proxy
    "GOLDBEES.NS",    # Gold Fund proxy
]

# ---------------------------------------------------------------------------
# F&O Active Stocks (most traded in Futures & Options)
# These are the stocks with highest F&O volume on NSE
# ---------------------------------------------------------------------------
FNO_ACTIVE = [
    # Heavy F&O volume — these drive most option premium
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "INFY.NS",
    "TCS.NS", "BAJFINANCE.NS", "AXISBANK.NS", "KOTAKBANK.NS", "LT.NS",
    "TATAMOTORS.NS", "ITC.NS", "BHARTIARTL.NS", "HCLTECH.NS", "MARUTI.NS",
    "TATASTEEL.NS", "HINDALCO.NS", "M&M.NS", "SUNPHARMA.NS", "WIPRO.NS",
    "ADANIENT.NS", "ADANIPORTS.NS", "TECHM.NS", "TITAN.NS", "POWERGRID.NS",
    "NTPC.NS", "ONGC.NS", "COALINDIA.NS", "JSWSTEEL.NS", "GRASIM.NS",
    "INDUSINDBK.NS", "BAJAJFINSV.NS", "ASIANPAINT.NS", "NESTLEIND.NS",
    "BRITANNIA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    "EICHERMOT.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "BPCL.NS", "UPL.NS",
    "SHRIRAMFIN.NS", "DLF.NS", "TATAPOWER.NS", "BANKBARODA.NS", "PNB.NS",
    "BEL.NS", "HAL.NS", "JINDALSTEL.NS", "TRENT.NS", "ZOMATO.NS",
    "IRCTC.NS", "VEDL.NS", "SAIL.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS",
]

# ---------------------------------------------------------------------------
# Currency Pairs (via yfinance)
# ---------------------------------------------------------------------------
CURRENCY_PAIRS = {
    "USD/INR": "USDINR=X",
    "EUR/INR": "EURINR=X",
    "GBP/INR": "GBPINR=X",
    "JPY/INR": "JPYINR=X",
    "USD/EUR": "EURUSD=X",
    "Gold/USD": "GC=F",
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
}

# ---------------------------------------------------------------------------
# Composite Lists (deduplicated)
# ---------------------------------------------------------------------------
NIFTY_100 = sorted(set(NIFTY_50 + NIFTY_NEXT_50))
NIFTY_200 = sorted(set(NIFTY_100 + NIFTY_200_EXTRA))
NIFTY_500 = sorted(set(NIFTY_200 + NIFTY_500_EXTRA))

# All unique NSE symbols (deduplicated)
ALL_NSE = sorted(set(
    NIFTY_500 + NIFTY_BANK + NIFTY_IT + NIFTY_PHARMA + NIFTY_AUTO +
    NIFTY_FMCG + NIFTY_METAL + NIFTY_ENERGY + NIFTY_REALTY + NIFTY_INFRA
))

# All unique BSE symbols
ALL_BSE = sorted(set(BSE_SENSEX_30 + BSE_200))

# BSE popular stocks with NSE suffix (for unified download)
BSE_POPULAR_NSE = [
    "ADANIGREEN.NS", "ADANITRANS.NS", "JSWENERGY.NS", "JINDALSTEL.NS",
    "MAZAGON.NS", "COCHINSHIP.NS",
]

# Full tradeable universe (stocks + ETFs)
FULL_UNIVERSE = sorted(set(ALL_NSE + ALL_BSE + NSE_ETFS + MF_PROXIES + BSE_POPULAR_NSE))


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_stocks_by_tier(tier: str) -> list[str]:
    """
    Get stock list by tier name.

    Args:
        tier: One of 'nifty50', 'nifty_next50', 'nifty100', 'nifty200',
              'nifty500', 'sensex30', 'bse200', 'bse_banks', 'bse_it',
              'bse_defence', 'bse_infra', 'bse_power', 'bse_realty',
              'bse_chemicals', 'bank', 'it', 'pharma', 'auto',
              'fmcg', 'metal', 'energy', 'realty', 'infra', 'all_nse', 'all_bse'

    Returns:
        List of stock symbols with exchange suffix (.NS or .BO)
    """
    tiers = {
        "nifty50": NIFTY_50,
        "nifty_next50": NIFTY_NEXT_50,
        "nifty100": NIFTY_100,
        "nifty200": NIFTY_200,
        "nifty500": NIFTY_500,
        "sensex30": BSE_SENSEX_30,
        "bse200": BSE_200,
        "bse_banks": BSE_BANKS,
        "bse_it": BSE_IT,
        "bse_defence": BSE_DEFENCE,
        "bse_infra": BSE_INFRA,
        "bse_power": BSE_POWER,
        "bse_realty": BSE_REALTY,
        "bse_chemicals": BSE_CHEMICALS,
        "bank": NIFTY_BANK,
        "it": NIFTY_IT,
        "pharma": NIFTY_PHARMA,
        "auto": NIFTY_AUTO,
        "fmcg": NIFTY_FMCG,
        "metal": NIFTY_METAL,
        "energy": NIFTY_ENERGY,
        "realty": NIFTY_REALTY,
        "infra": NIFTY_INFRA,
        "etfs": NSE_ETFS,
        "mf_proxies": MF_PROXIES,
        "fno": FNO_ACTIVE,
        "all_nse": ALL_NSE,
        "all_bse": ALL_BSE,
        "full_universe": FULL_UNIVERSE,
    }
    key = tier.lower().replace(" ", "_").replace("-", "_")
    if key not in tiers:
        raise ValueError(f"Unknown tier '{tier}'. Available: {list(tiers.keys())}")
    return tiers[key]


def strip_suffix(symbols: list[str]) -> list[str]:
    """Remove .NS / .BO suffix from symbols."""
    return [s.replace(".NS", "").replace(".BO", "") for s in symbols]


def to_bse(symbols: list[str]) -> list[str]:
    """Convert .NS symbols to .BO suffix for BSE."""
    return [s.replace(".NS", ".BO") for s in symbols]


def fetch_nifty500_live():
    """
    Fetch latest NIFTY 500 constituents using the niftystocks package.
    Falls back to the hardcoded list if the package is unavailable.

    Install: pip install niftystocks

    Returns:
        List of stock symbols with .NS suffix
    """
    try:
        from niftystocks import ns
        stocks = ns.get_nifty500_with_ns()
        if stocks and len(stocks) > 400:
            return stocks
    except ImportError:
        print("niftystocks package not installed. Using hardcoded NIFTY 500 list.")
        print("Install with: pip install niftystocks")
    except Exception as e:
        print(f"Failed to fetch live NIFTY 500 list: {e}")
    return NIFTY_500


def fetch_nse_equity_list():
    """
    Download the full NSE equity list (~2700+ stocks) from NSE India.
    This gives ALL traded stocks, not just index constituents.

    Returns:
        List of stock symbols with .NS suffix, or None on failure.
    """
    try:
        import pandas as pd
        # NSE provides a downloadable CSV of all listed equities
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        df = pd.read_csv(url)
        if "SYMBOL" in df.columns:
            symbols = [f"{s.strip()}.NS" for s in df["SYMBOL"].tolist()]
            return sorted(symbols)
    except Exception as e:
        print(f"Failed to fetch NSE equity list: {e}")
    return None


# ---------------------------------------------------------------------------
# Quick stats when run directly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("TradePilot Stock Universe")
    print("=" * 50)
    print(f"NIFTY 50:          {len(NIFTY_50)} stocks")
    print(f"NIFTY Next 50:     {len(NIFTY_NEXT_50)} stocks")
    print(f"NIFTY 100:         {len(NIFTY_100)} stocks")
    print(f"NIFTY 200:         {len(NIFTY_200)} stocks")
    print(f"NIFTY 500:         {len(NIFTY_500)} stocks")
    print(f"BSE SENSEX 30:     {len(BSE_SENSEX_30)} stocks")
    print(f"BSE 200:           {len(BSE_200)} stocks")
    print(f"ALL BSE unique:    {len(ALL_BSE)} stocks")
    print(f"NSE ETFs:          {len(NSE_ETFS)} ETFs")
    print(f"MF Proxies:        {len(MF_PROXIES)} AMCs/ETFs")
    print(f"F&O Active:        {len(FNO_ACTIVE)} stocks")
    print(f"Commodities:       {len(COMMODITIES)} futures/proxies")
    print(f"Currency Pairs:    {len(CURRENCY_PAIRS)} pairs")
    print(f"Market Indices:    {len(MARKET_INDICES)} indices")
    print(f"ALL NSE unique:    {len(ALL_NSE)} stocks")
    print(f"FULL UNIVERSE:     {len(FULL_UNIVERSE)} scoreable assets")
    print()
    print("NSE Sectoral indices:")
    for name in ["bank", "it", "pharma", "auto", "fmcg", "metal", "energy", "realty", "infra"]:
        print(f"  NIFTY {name.upper():8s}: {len(get_stocks_by_tier(name))} stocks")
    print()
    print("BSE Sectoral indices:")
    for name, label in [("bse_banks", "Banks"), ("bse_it", "IT"), ("bse_defence", "Defence"),
                         ("bse_infra", "Infra"), ("bse_power", "Power"), ("bse_realty", "Realty"),
                         ("bse_chemicals", "Chemicals")]:
        print(f"  BSE {label:10s}: {len(get_stocks_by_tier(name))} stocks")
    print()
    print("To fetch live NIFTY 500 list: pip install niftystocks")
    print("To fetch ALL NSE equities (~2700+): fetch_nse_equity_list()")
