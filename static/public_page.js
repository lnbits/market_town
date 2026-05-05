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
        recent_digests: []
      },
      worldSocket: null,
      paymentSocket: null,
      paymentDialog: {
        show: false
      },
      agentDialog: {
        show: false
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
      agentSession: null
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
    activeBusinessCount() {
      return this.publicState.businesses.filter(item => item.status !== 'closed')
        .length
    },
    availableSlotCount() {
      return this.publicState.districts.reduce(
        (total, item) => total + (item.available_slots || 0),
        0
      )
    }
  },
  methods: {
    satLabel(value) {
      return LNbits.utils.formatBalance(value || 0, 'sats')
    },
    floatLabel(value) {
      return Number(value || 0).toFixed(2)
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
    async fetchWorldState() {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/market_town/api/v1/public/world/${this.worldId}`,
          null
        )
        this.publicState = data
        if (!this.worldSocket) {
          this.connectWorldSocket()
        }
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async submitClaim() {
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
      }
    },
    copyInvoice() {
      if (!this.claimState.payment_request) return
      LNbits.utils.copyText(this.claimState.payment_request)
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
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/market_town/api/v1/agent/world/${this.worldId}/session`,
          null,
          null,
          {
            headers: {
              'X-API-Key': this.agentLookup.apiKey
            }
          }
        )
        this.agentSession = data
        this.agentDialog.show = false
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    connectWorldSocket() {
      try {
        const url = new URL(window.location)
        url.protocol = url.protocol === 'https:' ? 'wss' : 'ws'
        url.pathname = `/api/v1/ws/market-town-public-${this.worldId}`
        this.worldSocket = new WebSocket(url)
        this.worldSocket.onmessage = () => {
          this.fetchWorldState()
          if (this.agentSession && this.agentLookup.apiKey) {
            this.loadAgentSession()
          }
        }
        this.worldSocket.onclose = () => {
          this.worldSocket = null
        }
        this.worldSocket.onerror = () => {
          Quasar.Notify.create({
            type: 'warning',
            message:
              'World websocket disconnected. Refresh the page to reconnect.'
          })
        }
      } catch (error) {
        console.warn('Market Town world websocket failed', error)
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
          const payload = JSON.parse(event.data)
          if (payload.pending === false) {
            this.claimState.status = payload.status
            await this.fetchWorldState()
            if (this.claimState.claim_token) {
              await this.revealCredentials(this.claimState.claim_token)
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
