# Binance Public Data Pull: Operating Record

**Recorded:** 2026-07-15 (Asia/Shanghai)  
**Scope:** public Binance USD-M Futures data only; no API key, trading action, trigger change, or Paper permission.

## Active service

- **Scheduler:** Hermes cron job `binance-hourly-pull`, schedule `5 * * * *`.
- **Entrypoint:** `C:\Users\10639\AppData\Local\hermes\scripts\binance_data_puller.py`.
- **Storage root:** `C:\Users\10639\Desktop\加密\binance_free_db`.
- **Universe:** 40 contracts from this repository's `config/universe.json`, including `BTCUSDT` as benchmark.
- **Dimensions:** 1h klines, raw 8h funding plus 1h-aligned funding, 1h open interest, and 1h taker buy/sell volume.

## Reliability controls

- A full refresh takes an atomic single-instance lock at `binance_hourly_pull.lock`.  A live owner makes a second run exit safely; a lock whose owner PID is gone is reclaimed on the next run.
- Normal polling is sequential, with nine requests per batch and a one-second batch pause.
- Each request has a 15-second timeout.  The Taker dimension retries a transient network error, 429/418 rate limit, or 5xx response once after a conservative backoff (using `Retry-After` when supplied, otherwise 30 seconds for rate limits).
- Checkpoints advance only after successfully written data.  Consecutive failures are tracked; the checkpoint is not silently advanced.
- Full runs write timestamped Markdown reports under `binance_free_db\reports`.
- The report uses a 12-hour operational freshness budget for 8-hour funding and a 3-hour budget for the hourly dimensions.

## Verified run

The 10:05 scheduled run on 2026-07-15 completed at 10:07:23 local time.  The lock was created during execution, released afterward, and Hermes recorded the job as `ok`.

- Klines: 40/40 fresh after the run.
- Funding: raw funding files and checkpoints present for 40/40.
- Open interest: 40/40 fresh after the run.
- Taker buy/sell: the scheduled run initially refreshed 32/40.  A subsequent protected, Taker-only retry recovered six, leaving `1000PEPEUSDT` and `MUUSDT` pending after TLS/read-timeout failures.  Neither checkpoint was advanced; the 11:05 run will retry them.  A non-zero Taker result now propagates to Hermes rather than being shown as a false-green job.

The authoritative reports are `C:\Users\10639\Desktop\加密\binance_free_db\reports\pull_report_20260715_020723.md`, the protected retry report `C:\Users\10639\Desktop\加密\binance_free_db\reports\pull_report_20260715_021340.md`, and the final freshness-format verification `C:\Users\10639\Desktop\加密\binance_free_db\reports\pull_report_20260715_021648.md`.

## Safe operator checks

Run the read-only freshness check:

```powershell
python -B "C:\Users\10639\AppData\Local\hermes\scripts\binance_data_puller.py" --check
```

Do not start a manual full refresh while `binance_hourly_pull.lock` exists.  The entrypoint now enforces that rule itself.  CoinGlass remains out of scope: its separate Windows scheduled task is not used by this Binance service.
