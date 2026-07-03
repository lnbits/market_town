window.PageMarketTown = {
  template: '#page-market_town',
  data() {
    return {
      activeTab: 'economy',
      dashboard: {
        world: null,
        current_epoch: null,
        districts: [],
        business_types: [],
        agents: [],
        businesses: [],
        epochs: [],
        submissions: [],
        season_results: [],
        pending_payments: [],
        summary: {}
      },
      adminSocket: null,
      worldDialog: {
        show: false,
        mode: 'create',
        data: {}
      },
      districtDialog: {
        show: false,
        data: {}
      },
      businessTypeDialog: {
        show: false,
        data: {}
      }
    }
  },
  computed: {
    walletOptions() {
      return this.g.user.walletOptions || []
    },
    publicPageUrl() {
      if (!this.dashboard.world?.id) return '#'
      return `/market_town/${this.dashboard.world.id}`
    },
    summaryCards() {
      if (!this.dashboard.world) return []
      return [
        {
          label: 'World Status',
          value: this.dashboard.world.status,
          caption: this.dashboard.world.name
        },
        {
          label: 'Current Epoch',
          value: this.dashboard.current_epoch
            ? `#${this.dashboard.current_epoch.epoch_number}`
            : 'Idle',
          caption: this.dashboard.current_epoch
            ? this.dateLabel(
                this.dashboard.current_epoch.submission_deadline_at
              )
            : 'Starts with the first active business'
        },
        {
          label: 'Season',
          value: this.dashboard.world.current_season_number
            ? `#${this.dashboard.world.current_season_number}`
            : 'Idle',
          caption: `${this.dashboard.world.season_length_epochs} epochs`
        },
        {
          label: 'Active Businesses',
          value: `${this.dashboard.summary.active_businesses || 0}`,
          caption: `${this.dashboard.summary.pending_payments || 0} pending payments`
        }
      ]
    },
    districtColumns() {
      return [
        {name: 'name', label: 'District', field: 'name', align: 'left'},
        {
          name: 'footfall_base',
          label: 'Footfall',
          field: 'footfall_base',
          align: 'right'
        },
        {
          name: 'slot_limit',
          label: 'Slots',
          field: 'slot_limit',
          align: 'right'
        },
        {
          name: 'available_slots',
          label: 'Available',
          field: 'available_slots',
          align: 'right'
        },
        {
          name: 'occupied_slots',
          label: 'Occupied',
          field: 'occupied_slots',
          align: 'right'
        },
        {
          name: 'pending_slots',
          label: 'Pending',
          field: 'pending_slots',
          align: 'right'
        },
        {
          name: 'price_sensitivity',
          label: 'Price Sensitivity',
          field: 'price_sensitivity',
          align: 'right',
          format: value => this.floatLabel(value)
        },
        {
          name: 'quality_preference',
          label: 'Quality Preference',
          field: 'quality_preference',
          align: 'right',
          format: value => this.floatLabel(value)
        },
        {name: 'actions', label: '', field: 'actions', align: 'right'}
      ]
    },
    businessTypeColumns() {
      return [
        {name: 'name', label: 'Type', field: 'name', align: 'left'},
        {name: 'category', label: 'Category', field: 'category', align: 'left'},
        {
          name: 'open_fee_sat',
          label: 'Open Fee',
          field: 'open_fee_sat',
          align: 'right',
          format: value => this.satLabel(value)
        },
        {
          name: 'base_unit_cost_sat',
          label: 'Unit Cost',
          field: 'base_unit_cost_sat',
          align: 'right',
          format: value => this.satLabel(value)
        },
        {
          name: 'fixed_rent_sat',
          label: 'Rent',
          field: 'fixed_rent_sat',
          align: 'right',
          format: value => this.satLabel(value)
        },
        {
          name: 'base_capacity_units',
          label: 'Capacity',
          field: 'base_capacity_units',
          align: 'right'
        },
        {name: 'actions', label: '', field: 'actions', align: 'right'}
      ]
    },
    businessColumns() {
      return [
        {
          name: 'display_name',
          label: 'Business',
          field: 'display_name',
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
          name: 'reputation',
          label: 'Reputation',
          field: 'reputation',
          align: 'right',
          format: value => this.floatLabel(value)
        },
        {
          name: 'reliability',
          label: 'Reliability',
          field: 'reliability',
          align: 'right',
          format: value => this.floatLabel(value)
        },
        {
          name: 'quality_level',
          label: 'Quality',
          field: 'quality_level',
          align: 'right',
          format: value => this.floatLabel(value)
        },
        {name: 'actions', label: '', field: 'actions', align: 'right'}
      ]
    },
    agentColumns() {
      return [
        {
          name: 'display_name',
          label: 'Agent',
          field: 'display_name',
          align: 'left'
        },
        {name: 'status', label: 'Status', field: 'status', align: 'left'},
        {
          name: 'payout_lnaddress',
          label: 'Payout LN Address',
          field: 'payout_lnaddress',
          align: 'left'
        },
        {
          name: 'last_opened_at',
          label: 'Last Opened',
          field: 'last_opened_at',
          align: 'left',
          format: value => this.dateLabel(value)
        },
        {name: 'actions', label: '', field: 'actions', align: 'right'}
      ]
    },
    paymentColumns() {
      return [
        {
          name: 'payment_request_id',
          label: 'Claim',
          field: 'payment_request_id',
          align: 'left'
        },
        {name: 'status', label: 'Status', field: 'status', align: 'left'},
        {
          name: 'payment_hash',
          label: 'Payment Hash',
          field: 'payment_hash',
          align: 'left',
          format: value => this.shorten(value)
        },
        {
          name: 'paid_at',
          label: 'Paid',
          field: 'paid_at',
          align: 'left',
          format: value => this.dateLabel(value)
        }
      ]
    },
    epochColumns() {
      return [
        {
          name: 'epoch_number',
          label: 'Epoch',
          field: 'epoch_number',
          align: 'right'
        },
        {
          name: 'season_number',
          label: 'Season',
          field: 'season_number',
          align: 'right'
        },
        {name: 'status', label: 'Status', field: 'status', align: 'left'},
        {
          name: 'submission_deadline_at',
          label: 'Cutoff',
          field: 'submission_deadline_at',
          align: 'left',
          format: value => this.dateLabel(value)
        },
        {
          name: 'resolved_at',
          label: 'Resolved',
          field: 'resolved_at',
          align: 'left',
          format: value => this.dateLabel(value)
        }
      ]
    },
    submissionColumns() {
      return [
        {
          name: 'epoch_number',
          label: 'Epoch',
          field: 'epoch_number',
          align: 'right'
        },
        {
          name: 'business_id',
          label: 'Business',
          field: 'business_id',
          align: 'left',
          format: value => this.shorten(value)
        },
        {
          name: 'is_valid',
          label: 'Valid',
          field: 'is_valid',
          align: 'left',
          format: value => (value ? 'yes' : 'no')
        },
        {
          name: 'validation_error',
          label: 'Validation',
          field: 'validation_error',
          align: 'left'
        },
        {
          name: 'submitted_at',
          label: 'Submitted',
          field: 'submitted_at',
          align: 'left',
          format: value => this.dateLabel(value)
        }
      ]
    },
    seasonColumns() {
      return [
        {
          name: 'season_number',
          label: 'Season',
          field: 'season_number',
          align: 'right'
        },
        {
          name: 'epoch_start',
          label: 'Epoch Start',
          field: 'epoch_start',
          align: 'right'
        },
        {
          name: 'epoch_end',
          label: 'Epoch End',
          field: 'epoch_end',
          align: 'right'
        },
        {
          name: 'payout_status',
          label: 'Payout Status',
          field: 'payout_status',
          align: 'left'
        },
        {
          name: 'updated_at',
          label: 'Updated',
          field: 'updated_at',
          align: 'left',
          format: value => this.dateLabel(value)
        }
      ]
    }
  },
  methods: {
    emptyWorldForm() {
      return {
        name: '',
        wallet_id: this.walletOptions?.[0]?.value || null,
        fee_wallet_id: null,
        operator_fee_percent: 5,
        epoch_duration_hours: 4,
        submission_cutoff_minutes: 5,
        season_length_epochs: 42,
        status: 'active'
      }
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
    dateLabel(value) {
      return value ? LNbits.utils.formatDate(value) : '-'
    },
    shorten(value) {
      if (!value) return '-'
      return value.length > 12
        ? `${value.slice(0, 6)}...${value.slice(-4)}`
        : value
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
    openBootstrapDialog() {
      this.worldDialog.mode = 'create'
      this.worldDialog.data = this.emptyWorldForm()
      this.worldDialog.show = true
    },
    openWorldDialog() {
      this.worldDialog.mode = 'edit'
      this.worldDialog.data = {...this.dashboard.world}
      this.worldDialog.show = true
    },
    decimalField(value, digits = 2) {
      const number = Number(value)
      if (!Number.isFinite(number)) return ''
      return number.toFixed(digits).replace(/\.?0+$/, '')
    },
    syncDistrictDecimal(field, value) {
      const number = Number(value)
      this.districtDialog.data[field] = Number.isFinite(number)
        ? Number(number.toFixed(2))
        : null
    },
    editDistrict(row) {
      this.districtDialog.data = {
        ...row,
        affluence: this.decimalField(row.affluence),
        price_sensitivity: this.decimalField(row.price_sensitivity),
        quality_preference: this.decimalField(row.quality_preference)
      }
      this.districtDialog.show = true
    },
    editBusinessType(row) {
      this.businessTypeDialog.data = {...row}
      this.businessTypeDialog.show = true
    },
    async fetchDashboard(notifyMissing = false) {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/market_town/api/v1/admin/dashboard',
          null
        )
        this.dashboard = data
        if (!this.adminSocket) {
          this.connectAdminSocket()
        }
      } catch (error) {
        if (error?.response?.status === 404) {
          if (notifyMissing) {
            Quasar.Notify.create({
              type: 'info',
              message: 'Create your world to get started.'
            })
          }
          return
        }
        LNbits.utils.notifyApiError(error)
      }
    },
    async saveWorld() {
      const method = this.worldDialog.mode === 'create' ? 'POST' : 'PUT'
      const url =
        this.worldDialog.mode === 'create'
          ? '/market_town/api/v1/world/bootstrap'
          : '/market_town/api/v1/world'
      try {
        const source = this.worldDialog.data
        const data = {
          name: source.name,
          wallet_id: source.wallet_id,
          fee_wallet_id: source.fee_wallet_id,
          operator_fee_percent: source.operator_fee_percent,
          status: source.status,
          epoch_duration_hours: source.epoch_duration_hours,
          submission_cutoff_minutes: source.submission_cutoff_minutes,
          season_length_epochs: source.season_length_epochs,
          world_seed: source.world_seed
        }
        if (!data.fee_wallet_id) {
          data.fee_wallet_id = null
        }
        await LNbits.api.request(method, url, null, data)
        this.worldDialog.show = false
        await this.fetchDashboard()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async saveDistrict() {
      try {
        const source = this.districtDialog.data
        const data = {
          name: source.name,
          footfall_base: source.footfall_base,
          affluence: Number(source.affluence),
          price_sensitivity: Number(source.price_sensitivity),
          quality_preference: Number(source.quality_preference),
          slot_limit: source.slot_limit,
          config_text: source.config_text
        }
        await LNbits.api.request(
          'PUT',
          `/market_town/api/v1/districts/${this.districtDialog.data.id}`,
          null,
          data
        )
        this.districtDialog.show = false
        await this.fetchDashboard()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async saveBusinessType() {
      try {
        const source = this.businessTypeDialog.data
        const data = {
          name: source.name,
          category: source.category,
          open_fee_sat: source.open_fee_sat,
          base_unit_cost_sat: source.base_unit_cost_sat,
          fixed_rent_sat: source.fixed_rent_sat,
          base_capacity_units: source.base_capacity_units,
          config_text: source.config_text
        }
        await LNbits.api.request(
          'PUT',
          `/market_town/api/v1/business-types/${this.businessTypeDialog.data.id}`,
          null,
          data
        )
        this.businessTypeDialog.show = false
        await this.fetchDashboard()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async resetSeeds() {
      await LNbits.utils
        .confirmDialog('Reset seeded districts and business types?')
        .onOk(async () => {
          try {
            await LNbits.api.request(
              'POST',
              '/market_town/api/v1/world/reset-seeds',
              null
            )
            await this.fetchDashboard()
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    },
    async deleteWorld() {
      await LNbits.utils
        .confirmDialog('Delete this Market Town world and all its data?')
        .onOk(async () => {
          try {
            await LNbits.api.request(
              'DELETE',
              '/market_town/api/v1/world',
              null
            )
            this.dashboard = {
              world: null,
              current_epoch: null,
              districts: [],
              business_types: [],
              agents: [],
              businesses: [],
              epochs: [],
              submissions: [],
              season_results: [],
              pending_payments: [],
              summary: {}
            }
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    },
    async resolveEpochNow() {
      try {
        await LNbits.api.request(
          'POST',
          '/market_town/api/v1/epochs/resolve',
          null
        )
        await this.fetchDashboard()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async setAgentStatus(agent, status) {
      try {
        await LNbits.api.request(
          'PUT',
          `/market_town/api/v1/agents/${agent.id}/status?status=${status}`,
          null
        )
        await this.fetchDashboard()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async setBusinessStatus(business, status) {
      try {
        const businessId = business.id || business.business_id
        await LNbits.api.request(
          'PUT',
          `/market_town/api/v1/businesses/${businessId}/status?status=${status}`,
          null
        )
        await this.fetchDashboard()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async connectAdminSocket() {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/market_town/api/v1/admin/ws',
          null
        )
        const url = new URL(window.location)
        url.protocol = url.protocol === 'https:' ? 'wss' : 'ws'
        url.pathname = `/api/v1/ws/${data.channel}`
        this.adminSocket = new WebSocket(url)
        this.adminSocket.onmessage = () => {
          this.fetchDashboard()
        }
        this.adminSocket.onclose = () => {
          this.adminSocket = null
        }
        this.adminSocket.onerror = () => {
          Quasar.Notify.create({
            type: 'warning',
            message:
              'Admin websocket disconnected. Use manual actions to refresh.'
          })
        }
      } catch (error) {
        console.warn('Market Town admin websocket failed', error)
      }
    }
  },
  created() {
    this.fetchDashboard(true)
  },
  beforeUnmount() {
    if (this.adminSocket) {
      this.adminSocket.onclose = null
      this.adminSocket.close()
      this.adminSocket = null
    }
  }
}
