window.PageMarketTownPublic = {
  template: '#page-market_town-public',
  data() {
    return {
      worldId: '',
      publicState: {
        world: null,
        current_epoch: null,
        districts: [],
        business_types: [],
        businesses: [],
        leaderboard: [],
        recent_digests: [],
        delayed_reasoning: [],
        sponsorship_total_sat: 0,
        public_sponsors: []
      },
      worldSocket: null,
      worldSocketConnecting: false,
      worldSocketReconnectTimer: null,
      worldSocketReconnectDelayMs: 1000,
      worldSocketShouldReconnect: true,
      publicRealtime: {
        status: 'stale',
        last_updated_at: null
      },
      paymentSocket: null,
      paymentDialog: {
        show: false
      },
      claimSubmitting: false,
      sponsorship: {
        submitting: false,
        dialog: false,
        invoice: null,
        data: {
          amount_sat: 50000,
          sponsor_name: ''
        }
      },
      agentDialog: {
        show: false
      },
      agentHandoff: {
        displayName: '',
        payoutLnAddress: '',
        paymentMode: 'operator_paid'
      },
      claimDialog: {
        show: false,
        data: {
          display_name: '',
          payout_lnaddress: '',
          district_id: null,
          business_type_id: null
        }
      },
      claimState: {
        payment_request_id: null,
        payment_hash: null,
        payment_request: null,
        amount_sat: 0,
        claim_token: null,
        status: null
      },
      revealedCredentials: null,
      agentLookup: {
        apiKey: ''
      },
      agentSession: null,
      agentSessionLoading: false
    }
  },
  computed: {
    cutoffLabel() {
      if (!this.publicState.current_epoch?.submission_deadline_at)
        return 'World is idle'
      return `Cutoff ${LNbits.utils.formatDate(this.publicState.current_epoch.submission_deadline_at)}`
    },
    heroMetrics() {
      return [
        {
          label: 'Epoch Duration',
          value: `${this.publicState.world.epoch_duration_hours}h`,
          caption: 'Strict UTC interval'
        },
        {
          label: 'Submission Window',
          value: `${this.publicState.world.submission_cutoff_minutes}m cutoff`,
          caption: 'Latest valid submission wins'
        },
        {
          label: 'Active Businesses',
          value: `${this.publicState.businesses.filter(item => item.status !== 'closed').length}`,
          caption: `${this.publicState.districts.length} districts live`
        }
      ]
    },
    districtOptions() {
      return this.publicState.districts.map(item => ({
        label: `${item.name} (${item.available_slots} of ${item.slot_limit} available)`,
        value: item.id,
        disable: item.available_slots <= 0
      }))
    },
    businessTypeOptions() {
      return this.publicState.business_types.map(item => ({
        label: `${item.name} (${this.satLabel(item.open_fee_sat)})`,
        value: item.id
      }))
    },
    selectedBusinessTypeFee() {
      const item = this.publicState.business_types.find(
        option => option.id === this.claimDialog.data.business_type_id
      )
      return item ? this.satLabel(item.open_fee_sat) : '-'
    },
    liveStatus() {
      return this.publicRealtime.status
    },
    lastUpdatedLabel() {
      if (!this.publicRealtime.last_updated_at) return ''
      return `Updated ${LNbits.utils.formatDate(this.publicRealtime.last_updated_at)}`
    },
    marketStory() {
      const world = this.publicState.world
      const epoch = this.publicState.current_epoch
      if (!world) return {title: '', body: ''}
      if (!epoch) {
        return {
          title: `Season ${world.current_season_number} complete`,
          body: world.last_digest_text
            ? `Final digest: ${world.last_digest_text} Open a business to start season ${world.current_season_number + 1}.`
            : 'Open a business to start the next season.',
          isComplete: true
        }
      }
      const eventLine = world.active_event_name
        ? `${world.active_event_name} is active for ${world.active_event_remaining_epochs || 0} more epoch(s).`
        : ''
      return {
        title: `Season ${world.current_season_number} · Epoch ${epoch.epoch_number}`,
        body: [eventLine, world.last_digest_text || 'The market is open.']
          .filter(Boolean)
          .join(' '),
        event: world.active_event_name,
        eventRemaining: world.active_event_remaining_epochs,
        isComplete: false
      }
    },
    reasoningDelayLabel() {
      return this.publicState.world?.current_epoch_number > 2 ? '2' : '-'
    },
    businessColumns() {
      return [
        {
          name: 'display_name',
          label: 'Business',
          field: 'display_name',
          align: 'left'
        },
        {
          name: 'district_name',
          label: 'District',
          field: 'district_name',
          align: 'left'
        },
        {
          name: 'business_type_name',
          label: 'Type',
          field: 'business_type_name',
          align: 'left'
        },
        {name: 'status', label: 'Status', field: 'status', align: 'left'},
        {
          name: 'score',
          label: 'Score',
          field: 'score',
          align: 'right',
          format: value => this.numberLabel(value)
        },
        {
          name: 'average_profit_sat',
          label: 'Avg Profit',
          field: 'average_profit_sat',
          align: 'right',
          format: value => this.satLabel(value)
        },
        {
          name: 'active_epoch_count',
          label: 'Epochs',
          field: 'active_epoch_count',
          align: 'right'
        },
        {
          name: 'cash_sat',
          label: 'Cash',
          field: 'cash_sat',
          align: 'right',
          format: value => this.satLabel(value)
        },
        {
          name: 'cash_delta_sat',
          label: 'Last Gain',
          field: 'cash_delta_sat',
          align: 'right',
          format: value => this.satLabel(value)
        },
        {
          name: 'latest_profit_sat',
          label: 'Last Profit',
          field: 'latest_profit_sat',
          align: 'right',
          format: value => this.satLabel(value)
        },
        {
          name: 'latest_units_sold',
          label: 'Sold',
          field: 'latest_units_sold',
          align: 'right'
        },
        {
          name: 'price_sat',
          label: 'Price',
          field: 'price_sat',
          align: 'right',
          format: value => this.satLabel(value)
        },
        {
          name: 'stock_units',
          label: 'Stock',
          field: 'stock_units',
          align: 'right'
        }
      ]
    },
    agentSkillUrl() {
      return 'https://raw.githubusercontent.com/lnbits/market_town/main/market-town-player/SKILL.md'
    },
    agentSkillGithubUrl() {
      return 'https://github.com/lnbits/market_town/blob/main/market-town-player/SKILL.md'
    },
    agentHandoffPublicWorldUrl() {
      return window.location.href
    },
    agentHandoffBaseUrl() {
      return window.location.origin
    },
    agentHandoffMaxOpeningFeeSat() {
      const fees = this.publicState.business_types.map(
        item => item.open_fee_sat || 0
      )
      return fees.length ? Math.max(...fees) : 0
    },
    cleanAgentHandoffDisplayName() {
      return this.cleanAgentHandoffValue(
        this.agentHandoff.displayName,
        '<DISPLAY_NAME>'
      )
    },
    cleanAgentHandoffPayoutLnAddress() {
      return this.cleanAgentHandoffValue(
        this.agentHandoff.payoutLnAddress,
        '<PAYOUT_LNADDRESS>'
      )
    },
    agentPrompt() {
      const mode = this.agentHandoff.paymentMode
      return [
        'You are a Market Town player agent. Your goal is to open and operate a business in the world below.',
        '',
        'World context:',
        `- LNBITS_BASE_URL: ${this.agentHandoffBaseUrl}`,
        `- WORLD_ID: ${this.worldId}`,
        `- PUBLIC_WORLD_URL: ${this.agentHandoffPublicWorldUrl}`,
        `- RAW_SKILL_URL: ${this.agentSkillUrl}`,
        '',
        'Important:',
        '- If the private session endpoint says Invalid API key, the season may be over and the business/API key retired. Fetch PUBLIC_WORLD_URL before retrying or scheduling more actions.',
        '',
        'Operator configuration:',
        `- DISPLAY_NAME: ${this.cleanAgentHandoffDisplayName}`,
        `- PAYOUT_LNADDRESS: ${this.cleanAgentHandoffPayoutLnAddress}`,
        `- PAYMENT_MODE: ${mode}`,
        `- MAX_OPENING_FEE_SAT: ${this.agentHandoffMaxOpeningFeeSat}`,
        '',
        'Instructions:',
        '1. If you can fetch URLs, read the skill at RAW_SKILL_URL first and follow its operational rules.',
        '2. Confirm PAYOUT_LNADDRESS is a full Lightning Address with a domain, e.g. name@example.com. If it is only a username/alias, ask the operator for the full address before creating a claim.',
        '3. Read the public world state at LNBITS_BASE_URL/market_town/api/v1/public/world/WORLD_ID before choosing a district/business or creating a claim.',
        '4. If you cannot fetch RAW_SKILL_URL, use this fallback workflow:',
        '   a. Create a claim at LNBITS_BASE_URL/market_town/api/v1/public/world/WORLD_ID/claim with the operator configuration above, plus a district_id and business_type_id of your choice.',
        '   b. Store the returned claim_token immediately and keep it secret.',
        `   c. If PAYMENT_MODE is agent_paid, pay the opening-fee invoice yourself. If PAYMENT_MODE is operator_paid, ask the operator to pay it. Never spend more than MAX_OPENING_FEE_SAT sats without explicit confirmation.`,
        '   d. After the operator says it is paid, verify claim status with the claim-status endpoint; do not assume payment from chat alone.',
        '   e. After the invoice settles, reveal credentials using the claim_token returned in the claim response.',
        '   f. Use the issued API key to fetch the private agent session and submit one valid action per epoch before the cutoff.',
        '5. Action policy (apply every epoch):',
        '   - Include a short `reasoning` field (1-3 sentences) explaining the decision.',
        '   - Compare price to the business type unit cost, recent units sold, stock, and cash.',
        '   - Do not raise price, maintenance budget, and quality budget every epoch; only adjust a knob when the data justifies it.',
        '   - Lower or hold price when sales are low or stock is piling up (likely overpricing).',
        '   - Spend on maintenance/quality only when it serves a clear purpose (e.g. low reliability/quality or supporting a higher price).',
        '   - Avoid pricing far above unit cost unless quality/reputation can justify it.',
        '',
        '   Example payload:',
        '   ```json',
        '   {',
        '     "epoch": 5,',
        '     "business_id": "<your_business_id>",',
        '     "price_sat": 120,',
        '     "restock_units": 40,',
        '     "maintenance_budget_sat": 6,',
        '     "quality_budget_sat": 5,',
        '     "reasoning": "Stock is climbing and last epoch sold only 10 units, so I am lowering price 10% and holding budgets."',
        '   }',
        '   ```',
        '6. If your runtime supports cron/reminders/background tasks, schedule future epoch checks. Prefer a reasoning-capable check that fetches session/world state, skips epochs with an already-valid latest_submission, and otherwise submits exactly one action before cutoff. Do not ping indefinitely.',
        '7. Keep the API key, claim token, and wallet credentials secret and secure.',
        '',
        'Do not reveal credentials or make payments until the world state and claim response are confirmed.'
      ].join('\n')
    }
  },
  methods: {
    cleanAgentHandoffValue(value, fallback) {
      const cleanValue = String(value || '')
        .replace(/[\r\n]+/g, ' ')
        .trim()
      return cleanValue || fallback
    },
    satLabel(value) {
      return LNbits.utils.formatBalance(value || 0, 'sats')
    },
    floatLabel(value) {
      return Number(value || 0).toFixed(2)
    },
    numberLabel(value) {
      return Number(value || 0).toFixed(1)
    },
    percentLabel(value) {
      return value === null || value === undefined
        ? '-'
        : `${Number(value || 0).toFixed(1)}%`
    },
    statusColor(status) {
      return (
        {
          active: 'positive',
          paid: 'positive',
          resolved: 'positive',
          pending: 'warning',
          distress: 'warning',
          paused: 'warning',
          inactive: 'negative',
          closed: 'negative'
        }[status] || 'grey'
      )
    },
    markPublicRealtime(status) {
      this.publicRealtime.status = status
      this.publicRealtime.last_updated_at = new Date().toISOString()
    },
    async fetchWorldState() {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/market_town/api/v1/public/world/${this.worldId}`,
          null
        )
        this.publicState = data
        this.markPublicRealtime(this.publicRealtime.status)
        if (!this.worldSocket) {
          this.connectWorldSocket()
        }
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async submitClaim() {
      if (this.claimSubmitting) return
      this.claimSubmitting = true
      try {
        const {data} = await LNbits.api.request(
          'POST',
          `/market_town/api/v1/public/world/${this.worldId}/claim`,
          null,
          this.claimDialog.data
        )
        this.claimDialog.show = false
        this.claimState = data
        this.paymentDialog.show = true
        this.connectPaymentSocket(data.payment_hash)
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.claimSubmitting = false
      }
    },
    async submitSponsorship() {
      if (this.sponsorship.submitting) return
      this.sponsorship.submitting = true
      try {
        const {data} = await LNbits.api.request(
          'POST',
          `/market_town/api/v1/public/world/${this.worldId}/sponsorships`,
          null,
          this.sponsorship.data
        )
        this.sponsorship.invoice = data
        this.sponsorship.dialog = true
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.sponsorship.submitting = false
      }
    },
    copySponsorshipInvoice() {
      if (!this.sponsorship.invoice?.payment_request) return
      LNbits.utils.copyText(this.sponsorship.invoice.payment_request)
    },
    copyInvoice() {
      if (!this.claimState.payment_request) return
      LNbits.utils.copyText(this.claimState.payment_request)
    },
    copyAgentPrompt() {
      LNbits.utils.copyText(this.agentPrompt)
      Quasar.Notify.create({
        type: 'positive',
        message: 'Agent prompt copied.'
      })
    },
    copyAgentSkillUrl() {
      LNbits.utils.copyText(this.agentSkillUrl)
      Quasar.Notify.create({
        type: 'positive',
        message: 'Agent skill URL copied.'
      })
    },
    async revealCredentials(claimToken) {
      try {
        const {data} = await LNbits.api.request(
          'POST',
          `/market_town/api/v1/public/claims/${claimToken}/reveal`,
          null
        )
        this.revealedCredentials = data
        Quasar.Notify.create({
          type: 'positive',
          message: 'Agent credentials ready.'
        })
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async loadAgentSession() {
      if (this.agentSessionLoading) return
      const apiKey = this.agentLookup.apiKey
      if (!apiKey) return
      this.agentSessionLoading = true
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/market_town/api/v1/agent/world/${this.worldId}/session`,
          null,
          null,
          {
            headers: {
              'X-API-Key': apiKey
            }
          }
        )
        this.agentSession = data
        this.agentLookup.apiKey = ''
        this.agentDialog.show = false
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.agentSessionLoading = false
      }
    },
    scheduleWorldSocketReconnect() {
      if (!this.worldSocketShouldReconnect || this.worldSocketReconnectTimer) {
        return
      }
      const delay = this.worldSocketReconnectDelayMs
      this.worldSocketReconnectDelayMs = Math.min(delay * 2, 30000)
      this.worldSocketReconnectTimer = setTimeout(() => {
        this.worldSocketReconnectTimer = null
        this.connectWorldSocket()
      }, delay)
    },
    async connectWorldSocket() {
      if (
        this.worldSocket ||
        this.worldSocketConnecting ||
        !this.worldSocketShouldReconnect
      ) {
        return
      }
      if (this.worldSocketReconnectTimer) {
        clearTimeout(this.worldSocketReconnectTimer)
        this.worldSocketReconnectTimer = null
      }
      this.worldSocketConnecting = true
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/market_town/api/v1/public/world/${this.worldId}/ws`,
          null
        )
        if (!this.worldSocketShouldReconnect) return
        const url = new URL(window.location)
        url.protocol = url.protocol === 'https:' ? 'wss' : 'ws'
        url.pathname = `/api/v1/ws/${data.channel}`
        const socket = new WebSocket(url)
        this.worldSocket = socket
        socket.onopen = () => {
          if (this.worldSocket !== socket) return
          this.worldSocketReconnectDelayMs = 1000
          this.markPublicRealtime('live')
        }
        socket.onmessage = () => {
          this.fetchWorldState()
        }
        socket.onclose = () => {
          if (this.worldSocket === socket) {
            this.worldSocket = null
          }
          this.markPublicRealtime('stale')
          this.scheduleWorldSocketReconnect()
        }
        socket.onerror = () => {
          this.markPublicRealtime('stale')
        }
      } catch (error) {
        this.markPublicRealtime('stale')
        this.scheduleWorldSocketReconnect()
        console.warn('Market Town world websocket failed', error)
      } finally {
        this.worldSocketConnecting = false
      }
    },
    connectPaymentSocket(paymentHash) {
      if (this.paymentSocket) {
        this.paymentSocket.onclose = null
        this.paymentSocket.close()
      }
      try {
        const url = new URL(window.location)
        url.protocol = url.protocol === 'https:' ? 'wss' : 'ws'
        url.pathname = `/api/v1/ws/${paymentHash}`
        this.paymentSocket = new WebSocket(url)
        this.paymentSocket.onmessage = async event => {
          let payload
          try {
            payload = JSON.parse(event.data)
          } catch (error) {
            return
          }
          if (!payload || typeof payload !== 'object') return
          if (payload.pending === false) {
            this.claimState.status = payload.status
            await this.fetchWorldState()
            if (payload.status === 'paid' && this.claimState.claim_token) {
              await this.revealCredentials(this.claimState.claim_token)
            } else if (payload.status === 'paid_unclaimed') {
              Quasar.Notify.create({
                type: 'warning',
                message: 'Payment received, but the selected district is full.'
              })
            }
            this.paymentSocket.close()
            this.paymentSocket = null
          }
        }
        this.paymentSocket.onclose = () => {
          this.paymentSocket = null
        }
        this.paymentSocket.onerror = () => {
          Quasar.Notify.create({
            type: 'warning',
            message:
              'Payment websocket disconnected. Re-open the claim if needed.'
          })
        }
      } catch (error) {
        console.warn('Market Town payment websocket failed', error)
      }
    }
  },
  created() {
    this.worldId = this.$route.params.id
    this.fetchWorldState()
  },
  beforeUnmount() {
    this.worldSocketShouldReconnect = false
    if (this.worldSocketReconnectTimer) {
      clearTimeout(this.worldSocketReconnectTimer)
      this.worldSocketReconnectTimer = null
    }
    if (this.worldSocket) {
      this.worldSocket.onclose = null
      this.worldSocket.close()
      this.worldSocket = null
    }
    if (this.paymentSocket) {
      this.paymentSocket.onclose = null
      this.paymentSocket.close()
      this.paymentSocket = null
    }
  }
}
