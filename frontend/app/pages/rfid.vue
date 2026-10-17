<script setup lang="ts">
import { useParkingLiveSync } from '~/composables/useParkingLiveSync'
import {
  RFID_CARD_STATUS_ITEMS,
  RFID_SCAN_ACCEPTED_ITEMS,
  RFID_SCAN_GATE_ITEMS,
  RFID_VEHICLE_TYPE_ITEMS,
  GATE_COMMAND_STATUS_COLORS,
  fetchGateActivity,
  fetchRfidCards,
  fetchRfidScans,
  registerRfidCard,
  updateRfidCard
} from '~/data/rfid'
import type { GateCommandState, RfidCard, RfidScanEvent } from '~/data/rfid'
import { extractApiError } from '~/utils/extractApiError'
import { formatDate } from '~/utils/format/date'

const toast = useToast()

const tab = ref('cards')

// ---------------------------------------------------------------- cards
const cards = ref<RfidCard[]>([])
const cardsLoading = ref(false)
const cardSearch = ref('')
const cardStatusFilter = ref('')

const cardColumns = [
  { accessorKey: 'cardUid', header: 'Card UID' },
  { accessorKey: 'licensePlate', header: 'License Plate' },
  { accessorKey: 'vehicleType', header: 'Type' },
  { accessorKey: 'label', header: 'Label' },
  { accessorKey: 'status', header: 'Status' },
  { accessorKey: 'lastUsedAt', header: 'Last Used' },
  { id: 'actions', header: '' }
]

async function loadCards() {
  cardsLoading.value = true
  try {
    const result = await fetchRfidCards({
      search: cardSearch.value.trim() || undefined,
      status: cardStatusFilter.value ? [cardStatusFilter.value] : undefined
    })
    cards.value = result.data
  } catch (err) {
    toast.add({ title: extractApiError(err, 'Could not load RFID cards.'), color: 'error' })
  } finally {
    cardsLoading.value = false
  }
}

// ---------------------------------------------------------------- scans
const scans = ref<RfidScanEvent[]>([])
const scansLoading = ref(false)
const scanGateFilter = ref('')
const scanAcceptedFilter = ref('')

const scanColumns = [
  { accessorKey: 'createdAt', header: 'Time' },
  { accessorKey: 'gate', header: 'Gate' },
  { accessorKey: 'cardUid', header: 'Card UID' },
  { accessorKey: 'licensePlate', header: 'Plate' },
  { accessorKey: 'accepted', header: 'Result' },
  { accessorKey: 'reason', header: 'Reason' }
]

async function loadScans() {
  scansLoading.value = true
  try {
    const result = await fetchRfidScans({
      gate: scanGateFilter.value || undefined,
      accepted: scanAcceptedFilter.value === '' ? undefined : scanAcceptedFilter.value === 'accepted'
    })
    scans.value = result.data
  } catch (err) {
    toast.add({ title: extractApiError(err, 'Could not load RFID scan history.'), color: 'error' })
  } finally {
    scansLoading.value = false
  }
}

// ---------------------------------------------------------------- gate activity
const commands = ref<GateCommandState[]>([])
const activityLoading = ref(false)

const commandColumns = [
  { accessorKey: 'createdAt', header: 'Time' },
  { accessorKey: 'deviceCode', header: 'Device' },
  { accessorKey: 'command', header: 'Command' },
  { accessorKey: 'status', header: 'Status' },
  { accessorKey: 'ackedAt', header: 'Acked' },
  { accessorKey: 'message', header: 'Message' }
]

async function loadActivity() {
  activityLoading.value = true
  try {
    const result = await fetchGateActivity({ limit: 50 })
    commands.value = result.commands
  } catch (err) {
    toast.add({ title: extractApiError(err, 'Could not load gate activity.'), color: 'error' })
  } finally {
    activityLoading.value = false
  }
}

// ---------------------------------------------------------------- register / edit
const showCardModal = ref(false)
const savingCard = ref(false)
const cardFormError = ref('')
const editingUid = ref<string | null>(null)
const cardForm = reactive({
  cardUid: '',
  licensePlate: '',
  vehicleType: 'Car' as 'Car' | 'Motorcycle' | 'Truck',
  label: ''
})

function openRegister() {
  editingUid.value = null
  cardFormError.value = ''
  cardForm.cardUid = ''
  cardForm.licensePlate = ''
  cardForm.vehicleType = 'Car'
  cardForm.label = ''
  showCardModal.value = true
}

function openEdit(card: RfidCard) {
  editingUid.value = card.cardUid
  cardFormError.value = ''
  cardForm.cardUid = card.cardUid
  cardForm.licensePlate = card.licensePlate
  cardForm.vehicleType = card.vehicleType
  cardForm.label = card.label || ''
  showCardModal.value = true
}

async function saveCard() {
  if (!cardForm.cardUid.trim() || !cardForm.licensePlate.trim()) {
    cardFormError.value = 'Card UID and license plate are required.'
    return
  }
  savingCard.value = true
  cardFormError.value = ''
  try {
    if (editingUid.value) {
      await updateRfidCard(editingUid.value, {
        licensePlate: cardForm.licensePlate.trim(),
        vehicleType: cardForm.vehicleType,
        label: cardForm.label.trim()
      })
      toast.add({ title: `Card ${editingUid.value} updated.`, color: 'success' })
    } else {
      await registerRfidCard({
        cardUid: cardForm.cardUid.trim(),
        licensePlate: cardForm.licensePlate.trim(),
        vehicleType: cardForm.vehicleType,
        label: cardForm.label.trim() || undefined
      })
      toast.add({ title: `Card ${cardForm.cardUid.trim().toUpperCase()} registered.`, color: 'success' })
    }
    showCardModal.value = false
    await loadCards()
  } catch (err) {
    cardFormError.value = extractApiError(err, 'Could not save the card.')
  } finally {
    savingCard.value = false
  }
}

async function toggleCardStatus(card: RfidCard) {
  const next = card.status === 'Active' ? 'Blocked' : 'Active'
  try {
    await updateRfidCard(card.cardUid, { status: next })
    toast.add({ title: `Card ${card.cardUid} ${next.toLowerCase()}.`, color: next === 'Active' ? 'success' : 'warning' })
    await loadCards()
  } catch (err) {
    toast.add({ title: extractApiError(err, 'Could not change card status.'), color: 'error' })
  }
}

// ---------------------------------------------------------------- live updates
async function refreshAll(): Promise<void> {
  await Promise.all([loadCards(), loadScans(), loadActivity()])
}

onMounted(() => {
  void refreshAll()
})

useParkingLiveSync(() => {
  void refreshAll()
})
</script>

<template>
  <UDashboardPanel id="rfid" :ui="{ body: 'p-0 sm:p-4' }">
    <template #header>
      <UDashboardNavbar title="RFID Cards & Scans">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <UBadge color="neutral" variant="subtle" size="sm">{{ cards.length }} cards</UBadge>
            <UButton
              color="primary"
              icon="i-lucide-plus"
              size="xs"
              class="font-bold"
              @click="openRegister"
            >
              Register card
            </UButton>
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-refresh-cw"
              size="xs"
              :loading="cardsLoading || scansLoading || activityLoading"
              @click="refreshAll"
            >
              Refresh
            </UButton>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UTabs
        v-model="tab"
        class="w-full"
        :items="[
          { label: 'Cards', value: 'cards', icon: 'i-lucide-credit-card' },
          { label: 'Scan history', value: 'scans', icon: 'i-lucide-scan-line' },
          { label: 'Gate activity', value: 'activity', icon: 'i-lucide-radio-tower' }
        ]"
      />

      <!-- Cards -->
      <div v-if="tab === 'cards'" class="mt-4 space-y-3">
        <div class="flex flex-wrap items-center gap-2">
          <UInput
            v-model="cardSearch"
            icon="i-lucide-search"
            placeholder="Search UID / plate / label"
            size="sm"
            class="w-64"
            @keyup.enter="loadCards"
          />
          <USelect
            v-model="cardStatusFilter"
            :items="RFID_CARD_STATUS_ITEMS"
            size="sm"
            class="w-40"
            @update:model-value="loadCards"
          />
          <UButton size="sm" color="neutral" variant="soft" icon="i-lucide-search" @click="loadCards">Filter</UButton>
        </div>

        <UTable :data="cards" :columns="cardColumns" :loading="cardsLoading">
          <template #cardUid-cell="{ row }">
            <span class="font-mono font-bold">{{ row.original.cardUid }}</span>
          </template>
          <template #status-cell="{ row }">
            <UBadge :color="row.original.status === 'Active' ? 'success' : 'error'" variant="subtle">
              {{ row.original.status }}
            </UBadge>
          </template>
          <template #lastUsedAt-cell="{ row }">
            <span class="text-muted-foreground text-xs">
              {{ row.original.lastUsedAt ? formatDate(row.original.lastUsedAt) : '—' }}
            </span>
          </template>
          <template #actions-cell="{ row }">
            <div class="flex justify-end gap-1">
              <UButton
                size="xs"
                variant="soft"
                :color="row.original.status === 'Active' ? 'error' : 'success'"
                @click="toggleCardStatus(row.original)"
              >
                {{ row.original.status === 'Active' ? 'Block' : 'Activate' }}
              </UButton>
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                icon="i-lucide-pencil"
                @click="openEdit(row.original)"
              />
            </div>
          </template>
        </UTable>
      </div>

      <!-- Scan history -->
      <div v-else-if="tab === 'scans'" class="mt-4 space-y-3">
        <div class="flex flex-wrap items-center gap-2">
          <USelect
            v-model="scanGateFilter"
            :items="RFID_SCAN_GATE_ITEMS"
            size="sm"
            class="w-40"
            @update:model-value="loadScans"
          />
          <USelect
            v-model="scanAcceptedFilter"
            :items="RFID_SCAN_ACCEPTED_ITEMS"
            size="sm"
            class="w-40"
            @update:model-value="loadScans"
          />
        </div>

        <UTable :data="scans" :columns="scanColumns" :loading="scansLoading">
          <template #createdAt-cell="{ row }">
            <span class="text-xs">{{ formatDate(row.original.createdAt) }}</span>
          </template>
          <template #gate-cell="{ row }">
            <UBadge :color="row.original.gate === 'entry' ? 'info' : 'primary'" variant="subtle">
              {{ row.original.gate }}
            </UBadge>
          </template>
          <template #cardUid-cell="{ row }">
            <span class="font-mono font-bold">{{ row.original.cardUid }}</span>
          </template>
          <template #accepted-cell="{ row }">
            <UBadge :color="row.original.accepted ? 'success' : 'error'" variant="subtle">
              {{ row.original.accepted ? 'accepted' : 'rejected' }}
            </UBadge>
          </template>
          <template #reason-cell="{ row }">
            <span class="text-muted-foreground text-xs">{{ row.original.reason || '—' }}</span>
          </template>
        </UTable>
      </div>

      <!-- Gate command activity -->
      <div v-else class="mt-4 space-y-3">
        <UTable :data="commands" :columns="commandColumns" :loading="activityLoading">
          <template #createdAt-cell="{ row }">
            <span class="text-xs">{{ formatDate(row.original.createdAt) }}</span>
          </template>
          <template #deviceCode-cell="{ row }">
            <span class="font-mono text-xs">{{ row.original.deviceCode }}</span>
          </template>
          <template #command-cell="{ row }">
            <span class="font-mono text-xs font-bold">{{ row.original.command }}</span>
          </template>
          <template #status-cell="{ row }">
            <UBadge :color="GATE_COMMAND_STATUS_COLORS[row.original.status] || 'neutral'" variant="subtle">
              {{ row.original.status }}
            </UBadge>
          </template>
          <template #ackedAt-cell="{ row }">
            <span class="text-muted-foreground text-xs">
              {{ row.original.ackedAt ? formatDate(row.original.ackedAt) : '—' }}
            </span>
          </template>
          <template #message-cell="{ row }">
            <span class="text-muted-foreground text-xs">{{ row.original.message || '—' }}</span>
          </template>
        </UTable>
      </div>
    </template>
  </UDashboardPanel>

  <UModal v-model:open="showCardModal" :dismissible="!savingCard">
    <template #content>
      <div class="p-6 space-y-4">
        <div class="flex items-start gap-3">
          <div class="rounded-full bg-primary/10 p-2">
            <UIcon name="i-lucide-credit-card" class="size-6 text-primary" />
          </div>
          <div>
            <h3 class="text-lg font-bold">{{ editingUid ? 'Edit card' : 'Register new card' }}</h3>
            <p class="text-sm text-muted-foreground mt-1">
              {{
                editingUid
                  ? 'Update the plate, vehicle type or label for this card.'
                  : 'Tap the card on the gate reader to read its UID, then register it here.'
              }}
            </p>
          </div>
        </div>

        <UAlert v-if="cardFormError" color="error" variant="subtle" :title="cardFormError" />

        <div class="space-y-3">
          <UFormField label="Card UID (hex, e.g. 04A1B2C3)">
            <UInput
              v-model="cardForm.cardUid"
              placeholder="04A1B2C3"
              class="w-full font-mono uppercase"
              :disabled="!!editingUid"
            />
          </UFormField>
          <UFormField label="License plate">
            <UInput v-model="cardForm.licensePlate" placeholder="2A-1234" class="w-full uppercase" />
          </UFormField>
          <div class="grid grid-cols-2 gap-3">
            <UFormField label="Vehicle type">
              <USelect v-model="cardForm.vehicleType" :items="RFID_VEHICLE_TYPE_ITEMS" class="w-full" />
            </UFormField>
            <UFormField label="Label (optional)">
              <UInput v-model="cardForm.label" placeholder="Owner / notes" class="w-full" />
            </UFormField>
          </div>
        </div>

        <div class="flex justify-end gap-2">
          <UButton color="neutral" variant="ghost" :disabled="savingCard" @click="showCardModal = false">
            Cancel
          </UButton>
          <UButton color="primary" icon="i-lucide-check" :loading="savingCard" @click="saveCard">
            {{ editingUid ? 'Save changes' : 'Register card' }}
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>
