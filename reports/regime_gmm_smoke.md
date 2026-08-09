# Regime GMM Smoke (171)

- source: btc_bars n=39991
- components: 2 (sorted: k1 = higher total variance = stress)
- means:
[[-0.40384734 -0.39627426]
 [ 1.32987799  1.30493967]]
- vars:
[[0.25082949 0.24901427]
 [1.16139149 1.25303065]]
- weights: [0.76706383 0.23293617]
- n_iter: 43
- stress posterior mean: 0.2329
- stress posterior p90: 0.9991

## Usage rule

- Use as **filter / size scale** for s001 only after event-study shows lift.
- Do **not** trade the posterior itself.
- Next: join posterior asof onto wash_cvd events (script TBD, needs Owner research slot).
