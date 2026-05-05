empty_dict: dict[str, str] = {}


async def m001_initial(db):
    await db.execute(
        f"""
        CREATE TABLE market_town.worlds (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            wallet_id TEXT NOT NULL,
            fee_wallet_id TEXT,
            operator_fee_percent REAL NOT NULL DEFAULT 5,
            world_seed TEXT NOT NULL,
            epoch_duration_hours INTEGER NOT NULL,
            submission_cutoff_minutes INTEGER NOT NULL,
            season_length_epochs INTEGER NOT NULL,
            current_epoch_number INTEGER NOT NULL DEFAULT 0,
            current_season_number INTEGER NOT NULL DEFAULT 0,
            active_event_id TEXT,
            active_event_name TEXT,
            active_event_multiplier REAL NOT NULL DEFAULT 1.0,
            active_event_remaining_epochs INTEGER NOT NULL DEFAULT 0,
            last_resolved_epoch INTEGER NOT NULL DEFAULT -1,
            last_digest_text TEXT,
            started_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE market_town.world_districts (
            id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            district_key TEXT NOT NULL,
            name TEXT NOT NULL,
            footfall_base INTEGER NOT NULL DEFAULT 100,
            affluence REAL NOT NULL DEFAULT 1.0,
            price_sensitivity REAL NOT NULL DEFAULT 1.0,
            quality_preference REAL NOT NULL DEFAULT 1.0,
            slot_limit INTEGER NOT NULL DEFAULT 10,
            config_text TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE market_town.business_types (
            id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            type_key TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            open_fee_sat INTEGER NOT NULL DEFAULT 500,
            base_unit_cost_sat INTEGER NOT NULL DEFAULT 100,
            fixed_rent_sat INTEGER NOT NULL DEFAULT 10,
            base_capacity_units INTEGER NOT NULL DEFAULT 20,
            config_text TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE market_town.agents (
            id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            api_key_hash TEXT NOT NULL,
            payout_lnaddress TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            last_claimed_at TIMESTAMP,
            last_opened_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE market_town.businesses (
            id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            business_type_id TEXT NOT NULL,
            district_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            cash_sat INTEGER NOT NULL DEFAULT 0,
            reputation REAL NOT NULL DEFAULT 0.5,
            reliability REAL NOT NULL DEFAULT 0.7,
            quality_level REAL NOT NULL DEFAULT 0.5,
            price_sat INTEGER NOT NULL DEFAULT 100,
            stock_units INTEGER NOT NULL DEFAULT 0,
            missed_epochs INTEGER NOT NULL DEFAULT 0,
            distress_epochs INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            closed_at TIMESTAMP
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE market_town.epochs (
            id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            epoch_number INTEGER NOT NULL,
            season_number INTEGER NOT NULL,
            started_at TIMESTAMP NOT NULL,
            submission_deadline_at TIMESTAMP NOT NULL,
            digest_at TIMESTAMP NOT NULL,
            resolved_at TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'open',
            event_summary_text TEXT,
            digest_text TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE market_town.submissions (
            id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            epoch_number INTEGER NOT NULL,
            business_id TEXT NOT NULL,
            payload_text TEXT NOT NULL,
            is_valid BOOLEAN NOT NULL DEFAULT TRUE,
            validation_error TEXT,
            submitted_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE market_town.business_epoch_snapshots (
            id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            epoch_number INTEGER NOT NULL,
            business_id TEXT NOT NULL,
            units_sold INTEGER NOT NULL DEFAULT 0,
            revenue_sat INTEGER NOT NULL DEFAULT 0,
            profit_sat INTEGER NOT NULL DEFAULT 0,
            stock_before INTEGER NOT NULL DEFAULT 0,
            stock_after INTEGER NOT NULL DEFAULT 0,
            cash_before INTEGER NOT NULL DEFAULT 0,
            cash_after INTEGER NOT NULL DEFAULT 0,
            reputation_before REAL NOT NULL DEFAULT 0,
            reputation_after REAL NOT NULL DEFAULT 0,
            reliability_before REAL NOT NULL DEFAULT 0,
            reliability_after REAL NOT NULL DEFAULT 0,
            quality_before REAL NOT NULL DEFAULT 0,
            quality_after REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE market_town.season_results (
            id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            season_number INTEGER NOT NULL,
            epoch_start INTEGER NOT NULL,
            epoch_end INTEGER NOT NULL,
            leaderboard_text TEXT NOT NULL,
            payout_status TEXT NOT NULL DEFAULT 'pending',
            payout_summary_text TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE market_town.payment_requests (
            id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            district_id TEXT NOT NULL,
            business_type_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            payout_lnaddress TEXT NOT NULL,
            payment_hash TEXT NOT NULL,
            payment_request TEXT,
            amount_sat INTEGER NOT NULL,
            operations_amount_sat INTEGER NOT NULL DEFAULT 0,
            prize_pool_amount_sat INTEGER NOT NULL DEFAULT 0,
            lnbits_tribute_amount_sat INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            claim_token TEXT NOT NULL,
            agent_id TEXT,
            business_id TEXT,
            issued_api_key TEXT,
            credentials_revealed BOOLEAN NOT NULL DEFAULT FALSE,
            paid_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )

    await db.execute(
        f"""
        CREATE TABLE market_town.audit_events (
            id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            entity_id TEXT,
            payload_text TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
        """
    )
