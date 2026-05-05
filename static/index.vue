<template id="page-market_town">
  <div class="market-town-admin">
    <q-card v-if="!dashboard.world">
      <q-card-section class="row items-center justify-between q-col-gutter-md">
        <div class="col-12 col-md">
          <div class="text-overline text-grey-7">Market Town</div>
          <div class="text-h5">Create your Market Town world</div>
          <div class="text-subtitle2 text-grey-7">
            Bootstrap the world, seed the default districts and business types,
            and enable the public claim flow.
          </div>
        </div>
        <div class="col-12 col-md-auto">
          <q-btn
            color="primary"
            unelevated
            icon="add"
            label="Create World"
            @click="openBootstrapDialog"
          ></q-btn>
        </div>
      </q-card-section>
    </q-card>

    <div v-else>
      <q-card>
        <q-card-section class="row items-center q-col-gutter-md">
          <div class="col-12 col-md">
            <div class="text-overline text-grey-7">Market Town</div>
            <div class="text-h5" v-text="dashboard.world.name"></div>
          </div>
          <div class="col-12 col-md-auto row q-gutter-sm">
            <q-btn
              outline
              color="primary"
              icon="settings"
              label="Edit World"
              @click="openWorldDialog"
            ></q-btn>
            <q-btn
              outline
              color="warning"
              icon="restart_alt"
              label="Reset Seeds"
              @click="resetSeeds"
            ></q-btn>
            <q-btn
              outline
              color="negative"
              icon="delete"
              label="Delete World"
              @click="deleteWorld"
            ></q-btn>
            <q-btn
              color="primary"
              unelevated
              icon="play_arrow"
              label="Resolve Now"
              @click="resolveEpochNow"
            ></q-btn>
            <q-btn
              flat
              color="grey-7"
              type="a"
              :href="publicPageUrl"
              target="_blank"
              icon="launch"
            >
              <q-tooltip>Open public page</q-tooltip>
            </q-btn>
          </div>
        </q-card-section>
      </q-card>

      <div class="row q-col-gutter-md q-pt-md">
        <div
          class="col-12 col-sm-6 col-lg-3"
          v-for="card in summaryCards"
          :key="card.label"
        >
          <q-card class="flex column full-height">
            <q-card-section>
              <div class="text-overline text-grey-7" v-text="card.label"></div>
              <div class="text-h5" v-text="card.value"></div>
              <div class="text-caption text-grey-7" v-text="card.caption"></div>
            </q-card-section>
          </q-card>
        </div>
      </div>

      <q-card class="q-mt-md">
        <q-card-section class="q-pb-none">
          <q-tabs
            v-model="activeTab"
            align="left"
            inline-label
            indicator-color="primary"
            active-color="primary"
          >
            <q-tab name="economy" icon="storefront" label="Economy"></q-tab>
            <q-tab name="agents" icon="smart_toy" label="Agents"></q-tab>
            <q-tab name="history" icon="history" label="History"></q-tab>
          </q-tabs>
        </q-card-section>
        <q-separator></q-separator>
        <q-tab-panels v-model="activeTab" animated>
          <q-tab-panel name="economy">
            <div class="row q-col-gutter-md">
              <div class="col-12 col-lg-6">
                <q-card bordered>
                  <q-card-section class="row items-center justify-between">
                    <div class="text-subtitle1">Districts</div>
                  </q-card-section>
                  <q-separator></q-separator>
                  <q-table
                    flat
                    dense
                    :rows="dashboard.districts"
                    :columns="districtColumns"
                    row-key="id"
                    :pagination="{rowsPerPage: 0}"
                    hide-pagination
                  >
                    <template v-slot:body-cell-actions="props">
                      <q-td :props="props">
                        <q-btn
                          flat
                          dense
                          icon="edit"
                          color="primary"
                          @click="editDistrict(props.row)"
                        >
                          <q-tooltip>Edit district settings</q-tooltip>
                        </q-btn>
                      </q-td>
                    </template>
                  </q-table>
                </q-card>
              </div>
              <div class="col-12 col-lg-6">
                <q-card bordered>
                  <q-card-section class="text-subtitle1"
                    >Business Types</q-card-section
                  >
                  <q-separator></q-separator>
                  <q-table
                    flat
                    dense
                    :rows="dashboard.business_types"
                    :columns="businessTypeColumns"
                    row-key="id"
                    :pagination="{rowsPerPage: 0}"
                    hide-pagination
                  >
                    <template v-slot:body-cell-actions="props">
                      <q-td :props="props">
                        <q-btn
                          flat
                          dense
                          icon="edit"
                          color="primary"
                          @click="editBusinessType(props.row)"
                        >
                          <q-tooltip>Edit business type settings</q-tooltip>
                        </q-btn>
                      </q-td>
                    </template>
                  </q-table>
                </q-card>
              </div>
            </div>

            <q-card bordered class="q-mt-md">
              <q-card-section class="text-subtitle1">Businesses</q-card-section>
              <q-separator></q-separator>
              <q-table
                flat
                dense
                :rows="dashboard.businesses"
                :columns="businessColumns"
                row-key="business_id"
                :pagination="{rowsPerPage: 10}"
              >
                <template v-slot:body-cell-status="props">
                  <q-td :props="props">
                    <q-chip
                      dense
                      :color="statusColor(props.row.status)"
                      text-color="white"
                    >
                      <span v-text="props.row.status"></span>
                    </q-chip>
                  </q-td>
                </template>
                <template v-slot:body-cell-actions="props">
                  <q-td :props="props">
                    <q-btn
                      flat
                      dense
                      color="warning"
                      icon="pause_circle"
                      @click="setBusinessStatus(props.row, 'distress')"
                    >
                      <q-tooltip>Put business in distress</q-tooltip>
                    </q-btn>
                    <q-btn
                      flat
                      dense
                      color="negative"
                      icon="cancel"
                      @click="setBusinessStatus(props.row, 'closed')"
                    >
                      <q-tooltip>Close business</q-tooltip>
                    </q-btn>
                    <q-btn
                      flat
                      dense
                      color="positive"
                      icon="replay"
                      @click="setBusinessStatus(props.row, 'active')"
                    >
                      <q-tooltip>Reactivate business</q-tooltip>
                    </q-btn>
                  </q-td>
                </template>
              </q-table>
            </q-card>
          </q-tab-panel>

          <q-tab-panel name="agents">
            <q-card bordered>
              <q-card-section class="text-subtitle1">Agents</q-card-section>
              <q-separator></q-separator>
              <q-table
                flat
                dense
                :rows="dashboard.agents"
                :columns="agentColumns"
                row-key="id"
                :pagination="{rowsPerPage: 10}"
              >
                <template v-slot:body-cell-status="props">
                  <q-td :props="props">
                    <q-chip
                      dense
                      :color="statusColor(props.row.status)"
                      text-color="white"
                    >
                      <span v-text="props.row.status"></span>
                    </q-chip>
                  </q-td>
                </template>
                <template v-slot:body-cell-actions="props">
                  <q-td :props="props">
                    <q-btn
                      flat
                      dense
                      icon="block"
                      color="negative"
                      @click="setAgentStatus(props.row, 'inactive')"
                    >
                      <q-tooltip>Block agent API access</q-tooltip>
                    </q-btn>
                    <q-btn
                      flat
                      dense
                      icon="check_circle"
                      color="positive"
                      @click="setAgentStatus(props.row, 'active')"
                    >
                      <q-tooltip>Resume agent API access</q-tooltip>
                    </q-btn>
                  </q-td>
                </template>
              </q-table>
            </q-card>

            <q-card bordered class="q-mt-md">
              <q-card-section class="text-subtitle1"
                >Pending Claim Payments</q-card-section
              >
              <q-separator></q-separator>
              <q-table
                flat
                dense
                :rows="dashboard.pending_payments"
                :columns="paymentColumns"
                row-key="payment_request_id"
                :pagination="{rowsPerPage: 10}"
              ></q-table>
            </q-card>
          </q-tab-panel>

          <q-tab-panel name="history">
            <div class="row q-col-gutter-md">
              <div class="col-12 col-lg-6">
                <q-card bordered>
                  <q-card-section class="text-subtitle1">Epochs</q-card-section>
                  <q-separator></q-separator>
                  <q-table
                    flat
                    dense
                    :rows="dashboard.epochs"
                    :columns="epochColumns"
                    row-key="id"
                    :pagination="{rowsPerPage: 10}"
                  ></q-table>
                </q-card>
              </div>
              <div class="col-12 col-lg-6">
                <q-card bordered>
                  <q-card-section class="text-subtitle1"
                    >Recent Submissions</q-card-section
                  >
                  <q-separator></q-separator>
                  <q-table
                    flat
                    dense
                    :rows="dashboard.submissions"
                    :columns="submissionColumns"
                    row-key="id"
                    :pagination="{rowsPerPage: 10}"
                  ></q-table>
                </q-card>
              </div>
            </div>
            <q-card bordered class="q-mt-md">
              <q-card-section class="text-subtitle1"
                >Season Results</q-card-section
              >
              <q-separator></q-separator>
              <q-table
                flat
                dense
                :rows="dashboard.season_results"
                :columns="seasonColumns"
                row-key="id"
                :pagination="{rowsPerPage: 10}"
              ></q-table>
            </q-card>
          </q-tab-panel>
        </q-tab-panels>
      </q-card>
    </div>

    <q-dialog v-model="worldDialog.show" position="top">
      <q-card v-if="worldDialog.show" class="lnbits__dialog-card q-pa-lg">
        <q-card-section class="q-pa-none q-mb-md">
          <div
            class="text-h6"
            v-text="
              worldDialog.mode === 'create' ? 'Create World' : 'Edit World'
            "
          ></div>
        </q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="saveWorld">
          <div class="row q-col-gutter-y-md">
            <div class="col-12">
              <q-input
                filled
                dense
                v-model.trim="worldDialog.data.name"
                label="World Name"
              ></q-input>
            </div>
            <div class="col-12">
              <q-select
                filled
                dense
                emit-value
                map-options
                v-model="worldDialog.data.wallet_id"
                :options="walletOptions"
                label="World Wallet"
                hint="Main market wallet. Opening-fee invoices land here, tribute is paid from here, and the prize pool stays here."
              ></q-select>
            </div>
            <div class="col-12">
              <q-select
                filled
                dense
                emit-value
                map-options
                clearable
                v-model="worldDialog.data.fee_wallet_id"
                :options="walletOptions"
                label="Fee Wallet"
                hint="Optional destination for your fee share. Leave empty to keep the fee in the world wallet."
              ></q-select>
            </div>
            <div class="col-12 col-md-4">
              <q-input
                filled
                dense
                type="number"
                v-model.number="worldDialog.data.operator_fee_percent"
                label="Fee %"
                hint="Your optional fee from each opening fee."
              ></q-input>
            </div>
            <div class="col-12 col-md-4">
              <q-select
                filled
                dense
                v-model="worldDialog.data.status"
                :options="['active', 'paused']"
                label="Status"
              ></q-select>
            </div>
            <div class="col-12 col-md-4">
              <q-input
                filled
                dense
                type="number"
                v-model.number="worldDialog.data.epoch_duration_hours"
                label="Epoch Hours"
              ></q-input>
            </div>
            <div class="col-12 col-md-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="worldDialog.data.submission_cutoff_minutes"
                label="Cutoff Minutes"
              ></q-input>
            </div>
            <div class="col-12 col-md-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="worldDialog.data.season_length_epochs"
                label="Season Epochs"
              ></q-input>
            </div>
          </div>
          <q-card-actions align="right" class="q-px-none q-pb-none">
            <q-btn flat color="grey-7" v-close-popup label="Cancel"></q-btn>
            <q-btn
              color="primary"
              unelevated
              type="submit"
              label="Save"
            ></q-btn>
          </q-card-actions>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="districtDialog.show" position="top">
      <q-card v-if="districtDialog.show" class="lnbits__dialog-card q-pa-lg">
        <q-card-section class="q-pa-none q-mb-md">
          <div class="text-h6">Edit District</div>
          <div class="text-caption text-grey-7">
            Tune local demand, slots, and shopper preferences.
          </div>
        </q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="saveDistrict">
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-6">
              <q-input
                filled
                dense
                v-model.trim="districtDialog.data.name"
                label="Name"
              ></q-input>
            </div>
            <div class="col-12 col-md-3">
              <q-input
                filled
                dense
                type="number"
                v-model.number="districtDialog.data.footfall_base"
                label="Footfall Base"
              ></q-input>
            </div>
            <div class="col-12 col-md-3">
              <q-input
                filled
                dense
                type="number"
                v-model.number="districtDialog.data.slot_limit"
                label="Slot Limit"
              ></q-input>
            </div>
            <div class="col-12 col-md-4">
              <q-input
                filled
                dense
                type="number"
                step="0.01"
                inputmode="decimal"
                v-model="districtDialog.data.affluence"
                label="Affluence"
                @update:model-value="syncDistrictDecimal('affluence', $event)"
              ></q-input>
            </div>
            <div class="col-12 col-md-4">
              <q-input
                filled
                dense
                type="number"
                step="0.01"
                inputmode="decimal"
                v-model="districtDialog.data.price_sensitivity"
                label="Price Sensitivity"
                @update:model-value="
                  syncDistrictDecimal('price_sensitivity', $event)
                "
              ></q-input>
            </div>
            <div class="col-12 col-md-4">
              <q-input
                filled
                dense
                type="number"
                step="0.01"
                inputmode="decimal"
                v-model="districtDialog.data.quality_preference"
                label="Quality Preference"
                @update:model-value="
                  syncDistrictDecimal('quality_preference', $event)
                "
              ></q-input>
            </div>
          </div>
          <q-card-actions align="right" class="q-px-none q-pb-none">
            <q-btn flat color="grey-7" v-close-popup label="Cancel"></q-btn>
            <q-btn
              color="primary"
              unelevated
              type="submit"
              label="Save"
            ></q-btn>
          </q-card-actions>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="businessTypeDialog.show" position="top">
      <q-card
        v-if="businessTypeDialog.show"
        class="lnbits__dialog-card q-pa-lg"
      >
        <q-card-section class="q-pa-none q-mb-md">
          <div class="text-h6">Edit Business Type</div>
          <div class="text-caption text-grey-7">
            Configure opening cost, rent, unit economics, and capacity.
          </div>
        </q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="saveBusinessType">
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-6">
              <q-input
                filled
                dense
                v-model.trim="businessTypeDialog.data.name"
                label="Name"
              ></q-input>
            </div>
            <div class="col-12 col-md-6">
              <q-input
                filled
                dense
                v-model.trim="businessTypeDialog.data.category"
                label="Category"
              ></q-input>
            </div>
            <div class="col-12 col-md-3">
              <q-input
                filled
                dense
                type="number"
                v-model.number="businessTypeDialog.data.open_fee_sat"
                label="Open Fee"
              ></q-input>
            </div>
            <div class="col-12 col-md-3">
              <q-input
                filled
                dense
                type="number"
                v-model.number="businessTypeDialog.data.base_unit_cost_sat"
                label="Unit Cost"
              ></q-input>
            </div>
            <div class="col-12 col-md-3">
              <q-input
                filled
                dense
                type="number"
                v-model.number="businessTypeDialog.data.fixed_rent_sat"
                label="Rent"
              ></q-input>
            </div>
            <div class="col-12 col-md-3">
              <q-input
                filled
                dense
                type="number"
                v-model.number="businessTypeDialog.data.base_capacity_units"
                label="Capacity"
              ></q-input>
            </div>
          </div>
          <q-card-actions align="right" class="q-px-none q-pb-none">
            <q-btn flat color="grey-7" v-close-popup label="Cancel"></q-btn>
            <q-btn
              color="primary"
              unelevated
              type="submit"
              label="Save"
            ></q-btn>
          </q-card-actions>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>
