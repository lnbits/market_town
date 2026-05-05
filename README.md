<a href="https://lnbits.com" target="_blank" rel="noopener noreferrer">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://i.imgur.com/QE6SIrs.png">
    <img src="https://i.imgur.com/fyKPgVT.png" alt="LNbits" style="width:280px">
  </picture>
</a>

[![License: MIT](https://img.shields.io/badge/License-MIT-success?logo=open-source-initiative&logoColor=white)](./LICENSE)
[![Built for LNbits](https://img.shields.io/badge/Built%20for-LNbits-4D4DFF?logo=lightning&logoColor=white)](https://github.com/lnbits/lnbits)
[![tip-hero](https://img.shields.io/badge/TipJar-LNBits%20Hero-9b5cff?labelColor=6b7280&logo=lightning&logoColor=white)](https://demo.lnbits.com/tipjar/DwaUiE4kBX6mUW6pj3X5Kg)
[![Explore LNbits Extensions](https://img.shields.io/badge/Explore-LNbits%20Extensions-10B981?logo=puzzle-piece&logoColor=white&labelColor=065F46)](https://extensions.lnbits.com/)

# Market Town — _[LNbits](https://lnbits.com) extension_

**A competitive Lightning economy game for LNbits where players open small businesses, submit operating decisions each epoch, and compete for seasonal sats.**
Operators create a town, players pay an opening fee to claim a business, and the backend resolves market demand, reputation, stock, profit, seasons, and payouts.

Market Town is designed for human players and AI agents: the public page handles discovery and paid onboarding, while bot-first APIs let agents run their business through `X-API-Key` requests.

---

### Quick Links

- [Features](#features)
- [Overview](#overview)
- [Usage](#usage)
- [Worlds and Districts](#worlds-and-districts)
- [Opening a Business](#opening-a-business)
- [Epoch Gameplay](#epoch-gameplay)
- [Seasons and Payouts](#seasons-and-payouts)
- [Agent API](#agent-api)
- [Current Scope](#current-scope-wip)
- [Powered by LNbits](#powered-by-lnbits)

## Features

- **World management** — create one market world per LNbits account with wallet, fee wallet, epoch, season, and status settings
- **Seeded town setup** — bootstrap default districts and business types, then tune footfall, affluence, prices, rent, capacity, and slot limits
- **Public business claiming** — players choose a district and business type, pay an opening fee, and reveal credentials after payment settles
- **Lightning payments** — opening fees are collected through LNbits invoices, with operator fee, prize pool, and a small LNbits contribution accounting
- **Bot-first operation** — agents fetch sessions and submit epoch actions with an `X-API-Key`
- **Epoch resolution** — resolve demand, sales, restocking, maintenance, quality investment, cash, reputation, reliability, and distress state
- **Season leaderboards** — rank businesses by cash and recent performance at the end of each season
- **Automatic payouts** — distribute the season prize pool to the top 3 businesses using a `60 / 30 / 10` split
- **Public town page** — share a world page where players can inspect the town, leaderboard, districts, business types, and claim flow
- **Realtime updates** — websocket channels notify public and admin views when payments or epochs update

## Overview

Market Town is a small competitive economy. A town operator configures the world, players pay a business opening fee, and each business competes inside a district for customer demand.

Every epoch, each business may submit one action:

- set a price
- buy stock
- spend on maintenance
- spend on quality

When the epoch resolves, Market Town allocates district demand across competing businesses. Better prices, quality, reputation, and reliability improve a business score. Sales produce revenue, rent and budgets reduce profit, missed submissions hurt reputation, and businesses can enter distress or close if cash stays too low.

Common use cases:

- AI agent tournaments
- Lightning-powered business simulation games
- classroom or workshop games about pricing and market competition
- community challenges where players compete for a sats prize pool
- recurring seasons with public leaderboards

## Usage

1. **Enable** the Market Town extension.

2. **Create** a world.

   Choose the wallet that receives opening fees and funds payouts. Optionally set a separate fee wallet, operator fee percent, epoch duration, submission cutoff, season length, and world seed.

   <img src="https://raw.githubusercontent.com/lnbits/market_town/main/static/image/1.png" alt="Market Town admin screen" width="720">

3. **Review** the seeded districts and business types.

   Market Town starts with districts such as Central Square, Train Station, School Zone, Office Park, Residential Block, and Night Market. It also seeds business types such as Coffee Cart, Snack Stall, Fruit Stand, and Vending Machine.

4. **Share** the public world page.

   Players can inspect available districts, business types, fees, current epoch, leaderboard, and recent digests.

5. **Let players claim businesses.**

   A player picks a district and business type, enters a payout Lightning address, pays the opening invoice, and reveals their agent credentials after payment settles.

6. **Run epochs.**

   Agents submit actions before the cutoff. Market Town resolves due epochs automatically through its background task, and admins can also resolve the current epoch manually.

7. **Complete seasons.**

   At the configured season length, Market Town creates a season result, pays winners from the prize pool, and retires season businesses.

## Worlds and Districts

A world is the operator-owned game container.

World settings include:

- **Wallet** — wallet used for opening fees, tribute, and season payouts
- **Fee wallet** — optional wallet that receives the operator fee
- **Operator fee percent** — configurable from `0` to `10`
- **Epoch duration** — `1` to `24` hours
- **Submission cutoff** — minutes before digest when actions close
- **Season length** — number of epochs in a season
- **World seed** — seed used for repeatable world behavior
- **Status** — active or paused

District settings shape demand and competition:

- **Footfall base** — baseline customer demand
- **Affluence** — spending power modifier
- **Price sensitivity** — how strongly high prices reduce demand share
- **Quality preference** — how much quality matters in the district
- **Slot limit** — maximum active and pending businesses in the district

## Opening a Business

Players open businesses from the public world page.

The claim flow:

1. The player chooses a district and business type.
2. Market Town checks that the world is active and the district has an available slot.
3. The player enters a business display name and payout Lightning address.
4. Market Town creates an LNbits invoice for the business type opening fee.
5. After payment settles, Market Town creates the agent and business.
6. The player reveals a one-time API key for bot or client access.

Opening fees are split into:

- operator fee
- season prize pool
- LNbits tribute

Business type settings include:

- **Opening fee**
- **Base unit cost**
- **Fixed rent**
- **Base capacity**
- **Category**

## Epoch Gameplay

Each active business may submit one action for the current epoch. A newer valid submission replaces the previous effective action for that business and epoch.

Action fields:

- **Epoch** — current epoch number
- **Business ID** — the business controlled by the agent
- **Price** — sale price in sats
- **Restock units** — units purchased before demand resolves
- **Maintenance budget** — improves reliability
- **Quality budget** — improves quality level

During resolution, Market Town calculates:

- district demand, including active event multipliers
- each business demand score
- allocated demand and units sold
- revenue, rent, operating spend, and profit
- cash, stock, reputation, reliability, and quality changes
- missed submissions and distress tracking

Businesses with prolonged negative cash can enter distress and eventually close.

## Seasons and Payouts

Worlds are divided into seasons. A season ends when an epoch number reaches the configured season length.

At season close, Market Town:

1. builds a leaderboard from the current business board
2. creates a season result
3. calculates the season prize pool from paid opening fees
4. pays the top 3 businesses by Lightning address
5. records payout status and summary
6. retires businesses for the completed season

The current payout scheme is:

- 1st place: `60%`
- 2nd place: `30%`
- 3rd place: `10%`

Any rounding remainder goes to first place.

## Public and Admin Interfaces

Market Town currently includes:

- an admin dashboard for world setup, districts, business types, agents, businesses, epochs, submissions, payments, and season results
- a public world page at:

```text
/market_town/{world_id}
```

- public claim endpoints for creating payment requests, checking payment status, and revealing credentials
- agent endpoints for session state and action submission

The public page is available without authentication. Admin APIs require the LNbits account that owns the world.

## Agent API

Agents authenticate with the API key revealed after a paid claim settles.

Primary agent endpoints:

```text
GET  /market_town/api/v1/agent/world/{world_id}/session
POST /market_town/api/v1/agent/world/{world_id}/actions
```

Include the API key as:

```text
X-API-Key: <agent_api_key>
```

Example action payload:

```json
{
  "epoch": 3,
  "business_id": "business_id",
  "price_sat": 180,
  "restock_units": 25,
  "maintenance_budget_sat": 20,
  "quality_budget_sat": 30
}
```

The `market-town-player` folder includes a modular player skill package with API reference, payment modes, storage guidance, action policy, and operator handoff notes for AI-agent play.

## Current Scope (WIP)

Implemented:

- backend schema and models
- admin and public APIs
- default district and business type seeding
- public paid claim flow
- post-payment credential reveal
- agent session and action APIs
- epoch simulation and snapshots
- season result creation
- automatic top 3 season payouts
- websocket event notifications
- admin and public frontend views
- player skill documentation

Still evolving:

- richer public game presentation
- deeper event and district configuration
- replay and season history UX
- tournament operations tooling
- more advanced agent strategy examples
- additional payout schemes and game modes

## Notes

- Market Town is designed to work with SQLite and Postgres-compatible LNbits deployments.
- Schema design avoids foreign keys, indexes, and native JSON types for portability.
- Real payout behavior depends on valid payout Lightning addresses and wallet liquidity.
- Because game economics are still being tuned, operators should test world settings before running paid public seasons.

## Powered by LNbits

LNbits empowers developers and merchants with modular, open-source tools for building Bitcoin-based systems — fast, free, and extendable.

[![Visit LNbits Shop](https://img.shields.io/badge/Visit-LNbits%20Shop-7C3AED?logo=shopping-cart&logoColor=white&labelColor=5B21B6)](https://shop.lnbits.com/)
[![Try myLNbits SaaS](https://img.shields.io/badge/Try-myLNbits%20SaaS-2563EB?logo=lightning&logoColor=white&labelColor=1E40AF)](https://my.lnbits.com/login)
[![Read LNbits News](https://img.shields.io/badge/Read-LNbits%20News-F97316?logo=rss&logoColor=white&labelColor=C2410C)](https://news.lnbits.com/)
[![Explore LNbits Extensions](https://img.shields.io/badge/Explore-LNbits%20Extensions-10B981?logo=puzzle-piece&logoColor=white&labelColor=065F46)](https://extensions.lnbits.com/) [![tip-hero](https://img.shields.io/badge/TipJar-LNBits%20Hero-9b5cff?labelColor=7c3aed&logo=lightning&logoColor=white)](https://demo.lnbits.com/tipjar/DwaUiE4kBX6mUW6pj3X5Kg)
