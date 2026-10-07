# Public demo access · Judge evaluation

[Open Nexqori](https://nexqori.bmachuca-dev.com) · [Open the administrator panel](https://nexqori.bmachuca-dev.com/admin/complaints)

These credentials are intentionally public and belong only to the synthetic demo. No invitation or private file is needed.

| Role | Email / username | Password | Alternative document ID |
| --- | --- | --- | --- |
| Customer — Alex Torres | `cliente.demo@nexqori.com` | `Nexqori-Jurado-Cliente-2026!` | `JURADOCLIENTE` |
| Administrator | `admin.demo@nexqori.com` | `Nexqori-Jurado-Admin-2026!` | `JURADOADMIN` |

Use a normal browser window for the customer and an incognito window or separate browser for the administrator.

## Suggested evaluation

1. Sign in as the customer. Ask Nexi: **“My phone charge is higher than usual. Can you check it?”** The completed charge is **459 MXN**; the five previous payments average **299 MXN**.
2. Ask to prepare a complaint, review the draft, then say **“Confirm and send.”** The registered case appears in **My complaints**.
3. Sign in as the administrator. Open **Alex Torres** in the complaint panel. Review the summary and evidence, advance the case through delivery/review, approve the complaint and confirm its refund. If prompted for a password, use the administrator password above.
4. Return as the customer: **“What is the status of my case?”**, then **“Filter the results to show only the refund.”** The credited transaction appears in Transactions.
5. Optional: review **Mercado del Barrio**, 2,700 MXN against a usual average of 600 MXN. Recognize it as an occasional purchase; it remains excluded from the normal spending baseline.

English, Spanish and Portuguese are available. Voice requires microphone permission; the same complaint can be tested by text. These are shared accounts, so a previous evaluator may have completed the case. Existing cases can still be reviewed in My complaints. The login email addresses are test identifiers, not monitored inboxes.

## Recreate in a local demo

After following the root README and building the current API:

```sh
docker compose exec api python -m backend.jury_demo --confirm-public-demo
```

This opt-in command creates the two accounts and an independent scenario. Repeating it preserves existing activity and passwords; it does not reset another evaluator’s case. Never install these public accounts in a production bank.
