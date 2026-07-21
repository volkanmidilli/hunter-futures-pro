# SPEC-075 — Değerlendirme: research_universe / relative_strength / open_interest / research_market_data

**Tarih:** 2026-07-21
**Kapsam:** `src/hunter/research_universe/`, `src/hunter/relative_strength/`, `src/hunter/open_interest/`, `src/hunter/research_market_data/`
**Amaç:** Bu dört modülün `ranking-input.json` (SPEC-074 `pairlist_export` girdi kontratı) üretimine ne kadar yakın olduğunu tespit etmek.

---

## Önce bir düzeltme: Hiçbiri Binance'e (ya da başka bir borsaya) bağlanmıyor

Görev tanımında `research_universe` "Binance'ten pair listesi çekme", `research_market_data` ise "market data çekme" olarak nitelendirilmişti. Kod incelemesi bunun doğru olmadığını gösteriyor:

- `src/hunter` içinde (~90 paket) `ccxt`, `requests`, `python-binance` veya `from binance` importu **hiçbir yerde yok** — repo genelinde grep ile doğrulandı.
- `pyproject.toml` runtime bağımlılıkları sadece `pydantic>=2.0.0` ve `pyyaml>=6.0`; hiçbir HTTP istemcisi veya borsa SDK'sı yok.
- Dört modülün de `SafetyFlags` dataclass'ları `__post_init__` içinde network/exchange/database bağlantısını **zorunlu olarak False** yapıyor ve True verilirse `ValueError` fırlatıyor (fail-closed).
- `relative_strength` ve `open_interest`'in `FORBIDDEN_*_TERMS` kara listesinde literal `"binance"` string'i var — mimari olarak bu motorların borsaya asla dokunmaması bilinçli bir tasarım kararı.
- `research_market_data`, adından beklenenin aksine canlı veri çekmiyor; **yerel CSV dosyalarını okuyan, doğrulayan ve hizalayan** bir read-only pipeline.

Yani dört modül de "zaten bellekte olan veriyi işleyen" saf hesaplama/doğrulama motorları. Binance'ten veri çekme işi bu modüllerin **hiçbirinde yok ve mimari olarak da buraya girmesi engellenmiş**. Bu veri "içeri" nasıl giriyor sorusunun cevabı şu an sadece: `research_market_data` için elle hazırlanmış CSV dosyaları.

---

## 1. `src/hunter/research_universe/` — MVP-64 / SPEC-065

**Ne yapıyor:** Borsadan pair listesi çekmiyor. `ResearchMarketDataBundle` (CSV'den üretilmiş mum verisi), `ControlledUniverseReport` (discovery/controlled-universe motorundan) ve opsiyonel `PortfolioConstructionReport`'u girdi olarak alıp, iki paralel evren üretiyor:

- **Baseline universe** (`baseline.py`): Seçim penceresi içindeki ortalama quote-volume'a göre sıralanmış top-N pair (stablecoin, leveraged token, benchmark pair'ler ve coverage/pencere şartını sağlamayanlar elenir).
- **Candidate universe** (`candidate.py`): `ControlledUniverseReport`'taki `LONG_RESEARCH/SHORT_RESEARCH/NEUTRAL_RESEARCH` sınıflandırmasına sahip pair'ler; varsa `PortfolioConstructionReport`'taki `final_weight_pct`'e göre sıralanır, yoksa alfabetik.
- **Comparison** (`comparison.py`): İki evren arasında overlap/candidate-only/baseline-only/Jaccard benzerliği hesaplar.

Orkestrasyon `engine.py`'deki `build_research_universe_report(*, bundle, controlled_report, portfolio_report, config)` fonksiyonunda toplanıyor.

**Kullandığı "API'ler":** Hiçbir dış API yok. İç bağımlılıkları: `hunter.research_market_data`, `hunter.controlled_universe`, `hunter.portfolio_construction`, `hunter.discovery`, `hunter.controlled_universe_export_adapter`, `hunter.freqtrade_universe_adapter` (sadece model/reason-code importu).

**Girdi/Çıktı:**
- Girdi: `ResearchMarketDataBundle`, `ControlledUniverseReport`, opsiyonel `PortfolioConstructionReport`, `ResearchUniverseConfig` — hepsi zaten inşa edilmiş, bellekteki frozen dataclass'lar.
- Çıktı: `ResearchUniverseReport` (baseline + candidate + comparison + manifest + fingerprint), `writer.py` üzerinden JSON/Markdown'a serileştirilebiliyor.

**Dış bağımlılık:** Yok. Tamamen saf/deterministik, network/DB/dosya-okuma yasak (`ResearchUniverseSafetyFlags` ile fail-closed).

**Durum:** **Çalışır durumda.** `tests/test_research_universe/` altında `test_baseline.py`, `test_candidate.py`, `test_eligibility.py`, `test_engine.py`, `test_integration.py`, `test_models.py`, `test_writer.py` mevcut; tüm test paketi (4 modül toplam) çalıştırıldığında **488 test, 0 hata** ile geçiyor. Taslak değil, tamamlanmış ve test edilmiş bir motor.

**`ranking-input.json` için eksik olan:**
- `ranking-input.json`'daki `eligible_pairs` alanı muhtemelen candidate/baseline `pairs` listesinden türetilecek, ama bu dönüşümü yapan bir fonksiyon **yok**.
- `universe_total` alanı için `bundle`'daki toplam candidate sayısı (veya baseline+candidate union'ı) kullanılabilir, ama bunu net biçimde tanımlayan bir kural/fonksiyon yok.
- `research_universe`'ü besleyen `ControlledUniverseReport`/`PortfolioConstructionReport`/`ResearchMarketDataBundle`'ın günlük olarak nasıl/ne zaman inşa edileceğine dair bir orkestrasyon (CLI komutu, scheduler, "hunter universe refresh" gibi) bu paketin içinde yok — `docs/research/pairlist_export.md`'de bahsedilen `hunter universe refresh` CLI'si ayrı bir iş.

---

## 2. `src/hunter/relative_strength/` — MVP-24 / SPEC-025

**Ne yapıyor:** Coin'lerin BTC/ETH'e göre relative strength'ini hesaplıyor. `engine.py` içindeki `build_relative_strength_report(*, universe, btc_benchmark, eth_benchmark=None, config=None, ...)` fonksiyonu:

- Her coin için 7/14/30 günlük dönem getirisini BTC/ETH'e göre hesaplıyor.
- Ratio trend'i (coin/BTC oranının OLS eğimi) çıkarıyor.
- 30 günlük rank percentile hesaplıyor.
- Ağırlıklı alt-skorları birleştirip `total_score` (0-100) ve `OUTPERFORMER/NEUTRAL/UNDERPERFORMER` kararını üretiyor (3 dönemde de tutarlı işaret şartıyla).

Docstring açıkça belirtiyor: "All functions are pure computations over already-loaded in-memory values. No file I/O, network access, database access, or external resource access is performed."

**Kullandığı "API'ler":** Yok. Girdi olarak `btc_benchmark`/`eth_benchmark` OHLCV serilerini **çağıranın** sağlaması gerekiyor — motor bunları kendisi çekmiyor; boş verilirse `MISSING_BTC_BENCHMARK` ile bloklanır.

**Girdi/Çıktı:**
- Girdi: `RelativeStrengthInput(symbol, rows: OhlcvRow[])` listesi + BTC/ETH benchmark OHLCV serileri + `RelativeStrengthConfig`.
- Çıktı: `RelativeStrengthReport` → `scores: RelativeStrengthScore[]`. Her `RelativeStrengthScore`: `symbol`, `state`, `decision`, `total_score: float` (0-100), `rank_percentile_30d`, `sub_scores`, `data_quality: RelativeStrengthDataQuality`, `reason_codes`.
- `writer.py` üzerinden JSON (`relative_strength_report_to_dict`/`_to_json_text`), CSV ve Markdown'a serileştirilebiliyor.

**Dış bağımlılık:** Yok.

**Durum:** **Çalışır durumda.** `tests/test_relative_strength/` içinde engine/models/writer/integration testleri mevcut, toplam test paketinin parçası olarak geçiyor.

**`ranking-input.json` için eksik olan:**
- `RelativeStrengthScore.total_score` **plain `float`** (0-100 aralığında); `ranking-input.json`'daki `rs_scores` ise `dict[str, Decimal | None]` (JSON'da decimal-string, örn. `"88.1"`) bekliyor. **float → Decimal/string dönüşümü yapan bir adaptör yok.**
- `data_quality` alanı için: `RelativeStrengthReport`'taki `data_quality` zaten `expected_rows`/`actual_rows` gibi alanlar içeriyor (bkz. `open_interest` ile aynı şekil — `OpenInterestDataQuality`), ama `ranking-input.json`'ın beklediği tek-değerli yüzde (`"100"` gibi) formatına çeviren bir hesap/adaptör yok.
- `INSUFFICIENT_DATA`/`BLOCKED` durumundaki skorların `null` olarak `rs_scores`'a yazılması gerekiyor (kontrat `Decimal | None` diyor) — bu eşleme mantığı da henüz yazılmamış.
- Motoru gerçek BTC/ETH benchmark ve coin OHLCV verisiyle günlük olarak çalıştıran bir orkestrasyon (muhtemelen `research_market_data.build_relative_strength_run_inputs` üzerinden) var (`build_relative_strength_run_inputs` adaptörü mevcut ve çalışıyor), ama bu, `ranking-input.json` yazımına kadar uzanmıyor.

---

## 3. `src/hunter/open_interest/` — MVP-25 / SPEC-026

**Ne yapıyor:** Open Interest + fiyat + funding rate verisinden pozisyonlama/skor çıkarıyor. `engine.py`'deki `build_open_interest_report(*, universe, config=None, ...)`:

- 1/3/7/14 günlük OI ve fiyat değişimlerini hesaplıyor.
- `PRICE_UP_OI_UP` / `PRICE_DOWN_OI_DOWN` vb. pozisyonlama sınıflandırması yapıyor.
- OI trendini (`EXPANDING/CONTRACTING/FLAT/UNSTABLE`) ve funding context'i (`POSITIVE/NEGATIVE/NEUTRAL`) çıkarıyor.
- Ağırlıklı alt-skorlarla `total_score` (0-100) üretiyor.

`relative_strength`'in aksine dış benchmark gerektirmiyor (BTC/ETH karşılaştırması yok, sadece pair'in kendi OI/fiyat/funding geçmişi).

**Kullandığı "API'ler":** Yok. `OpenInterestInput(pair, rows: OpenInterestObservation[], metadata)` — veri çağıran tarafından sağlanmalı.

**Girdi/Çıktı:**
- Girdi: `OpenInterestInput[]` (her biri `OpenInterestObservation`: timestamp, open_interest, close, opsiyonel funding_rate) + `OpenInterestConfig`.
- Çıktı: `OpenInterestReport` → `scores: OpenInterestScore[]`. Her skor: `pair`, `state`, `positioning`, `trend`, `funding_context`, `total_score: float` (0-100), `data_quality: OpenInterestDataQuality` (`expected_rows`, `actual_rows`, `missing_rows`, `min_required_rows_met`, `stale_input_count`), `reason_codes`.
- `writer.py` ile JSON/CSV/Markdown çıktısı var.

**Dış bağımlılık:** Yok.

**Durum:** **Çalışır durumda.** `tests/test_open_interest/` içinde engine/models/writer/integration testleri var, tüm suite geçiyor.

**`ranking-input.json` için eksik olan:**
- Aynı `float → Decimal/string` dönüşüm eksikliği (`total_score` burada da plain `float`).
- **Daha kritik bir boşluk:** `research_market_data` paketinde `relative_strength` (`build_relative_strength_run_inputs`) ve `discovery` (`build_discovery_input_bundle`) için hazır adaptörler var, ama **`open_interest` için CSV/bundle'dan `OpenInterestInput`/`OpenInterestObservation` üreten hiçbir adaptör yok.** Open Interest ve funding rate verisi zaten OHLCV CSV formatında değil (ayrı bir veri kaynağı gerektirir — borsanın OI/funding endpoint'i), bu yüzden `research_market_data`'nın mevcut CSV-yükleme mimarisi bu veriyi hiç kapsamıyor. Yani open_interest motoru çalışır durumda olsa da, **onu besleyecek gerçek veri kaynağı/adaptör hattı proje genelinde hiçbir yerde yok** — bu, dört modül içindeki en büyük boşluk.

---

## 4. `src/hunter/research_market_data/` — MVP-63 / SPEC-064

**Ne yapıyor:** Canlı veri çekmiyor; **yerel CSV dosyalarından mum verisi okuyan, doğrulayan, kıyaslama (BTC/ETH) ile hizalayan ve `relative_strength`/`discovery` motorlarına adapte eden** read-only pipeline. Akış:

1. `csv_loader.load_csv_file` — CSV'yi okur (`date/open/high/low/close/volume` kolonlarını alias'larla eşler), SHA-256 file hash üretir, `data/` ve `reports/` altındaki yolları güvenlik gereği reddeder (`FORBIDDEN_PATH`).
2. `validator.build_normalized_candles` / `detect_timeframe` — ham satırları normalize edip timeframe tespiti yapar.
3. `aligner.align_candidate` / `build_candle_series` — coin serisini BTC/ETH benchmark'larıyla zaman ekseninde hizalar.
4. `engine.build_research_market_data_bundle(*, config, candidate_specs, btc_spec, eth_spec=None, ...)` — hepsini birleştirip `ResearchMarketDataBundle` üretir (uygun olmayan candidate'lar `exclusions`'a düşer, tüm candidate'lar elenirse `ALL_CANDIDATES_EXCLUDED` ile bloklanır).
5. `adapters.py` — `build_relative_strength_run_inputs(bundle)` ile `RelativeStrengthInput`'lara, `build_discovery_input_bundle(report)` ile discovery girdilerine çeviriyor.

**Kullandığı "API'ler":** Yok — sadece yerel dosya sistemi (`Path.read_text`, `csv.DictReader`). Network/DB bağlantısı `MarketDataSafetyFlags` ile zorunlu kapalı.

**Girdi/Çıktı:**
- Girdi: `MarketDataFileSpec` (dosya yolu + opsiyonel `expected_symbol`/`source_label`) listesi (candidate'lar) + BTC/ETH için ayrı `MarketDataFileSpec` + `ResearchMarketDataConfig`.
- Çıktı: `ResearchMarketDataBundle` (candidates, btc_series, eth_series, exclusions, manifest+fingerprint'ler). `writer.py` ile JSON/Markdown serileştirme mevcut.

**Dış bağımlılık:** Yok. Python standart kütüphanesi (`csv`, `hashlib`, `pathlib`) dışında bir şey kullanmıyor.

**Durum:** **Çalışır durumda.** `tests/test_research_market_data/` altında csv_loader/aligner/validator/symbol_normalizer/adapters/engine/writer/integration testleri mevcut ve geçiyor.

**`ranking-input.json` için eksik olan:**
- Bu modül zaten "besleme" katmanı olduğu için doğrudan `ranking-input.json` üretmiyor — ama CSV dosyalarının **nereden geldiği** (yani gerçek Binance/başka borsa fiyat verisinin CSV'ye nasıl dönüştüğü) proje genelinde hiçbir yerde otomatize değil. Şu an akış tamamen elle hazırlanmış CSV dosyalarına dayanıyor.
- Open Interest verisi için (yukarıda bahsedildiği gibi) hiçbir CSV şeması/adaptörü yok — bu paket sadece OHLCV mum verisini kapsıyor.

---

## Genel Özet

| Modül | Dış API/Binance bağımlılığı | Durum | Test kapsamı |
|---|---|---|---|
| `research_universe` | Yok | Çalışır | ✅ (baseline/candidate/eligibility/engine/comparison/writer/integration) |
| `relative_strength` | Yok | Çalışır | ✅ (engine/models/writer/integration) |
| `open_interest` | Yok | Çalışır | ✅ (engine/models/writer/integration) |
| `research_market_data` | Yok (yerel CSV) | Çalışır | ✅ (csv_loader/aligner/validator/adapters/engine/writer/integration) |

**Toplam:** 4 modülün birleşik test paketi **488 test, 0 hata** ile geçiyor — hiçbiri taslak değil, hepsi mimari olarak tamamlanmış ve iyi test edilmiş.

### `ranking-input.json` üretimi için asıl eksik: "glue step"

`docs/research/pairlist_export.md` bunu açıkça belgeliyor:

> "Producing that JSON from live `relative_strength`/`open_interest`/`research_universe` reports is a separate, not-yet-built glue step — out of SPEC-074's implement-only scope."

Bu değerlendirmenin doğruladığı somut eksik parçalar:

1. **Veri kaynağı otomasyonu yok:** `research_market_data` sadece elle sağlanmış CSV'leri okuyor; gerçek piyasa verisinin (fiyat) CSV'ye dönüşümü hiçbir yerde otomatik değil. Binance'ten (veya başka borsadan) veri çekme işi mimari olarak bilinçli şekilde bu paketlerin **dışında** tutulmuş — ayrı bir "ingestion" bileşeni gerekiyor.
2. **Open Interest veri kaynağı tamamen eksik:** `open_interest` motorunu besleyecek CSV şeması/adaptörü hiç yok (relative_strength ve discovery için var). OI/funding rate verisi OHLCV'den farklı bir kaynak gerektirdiği için bu, dört modül içindeki en büyük boşluk.
3. **`float` → `Decimal`/string dönüşümü yok:** `RelativeStrengthScore.total_score` ve `OpenInterestScore.total_score` plain `float`; `ranking-input.json` kontratı `Decimal | None` (JSON'da decimal-string) bekliyor. Bu dönüşümü (ve `INSUFFICIENT_DATA`/`BLOCKED` durumlarını `null`'a eşlemeyi) yapan kod yok.
4. **`data_quality` alanının tek-değer yüzdeye indirgenmesi yok:** Her iki motorun da `data_quality` (expected/actual/missing rows) alanları var, ama `ranking-input.json`'daki basit `dict[str, Decimal]` yüzde formatına çeviren hesap yok.
5. **`eligible_pairs`/`universe_total` türetme mantığı yok:** `research_universe`'ün candidate/baseline `pairs` listesinden bu iki alanı nasıl türeteceğine dair (hangi evren esas alınacak, nasıl birleştirilecek) tanımlı bir kural veya fonksiyon yok.
6. **Günlük orkestrasyon/CLI eksik:** `docs/research/pairlist_export.md`'de bahsedilen `hunter universe refresh` / `hunter coins rank` gibi komutlar `pairlist_export` tarafında (JSON dosyasını **tüketen** taraf) mevcut, ama JSON dosyasını **üreten** taraf — yani üç motoru sırayla çalıştırıp `ranking-input.json`'ı yazan bir CLI komutu veya scheduled job — hiçbir yerde yok.

**Sonuç:** Dört motor da (baseline/candidate universe, RS, OI, market-data ingestion) sağlam, test edilmiş, tek başına çalışan bileşenler. Eksik olan şey yeni bir motor değil; bu dört motorun çıktısını `ranking-input.json` şemasına döken, ayrı ve nispeten küçük bir **adaptör/orkestrasyon katmanı** (tip dönüşümü + veri kaynağı bağlama + CLI wiring) — ve open_interest tarafında ayrıca bir **veri kaynağı/adaptör** eksikliği.
