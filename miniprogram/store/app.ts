import { fetchBootstrap, fetchBookingOptions } from '../services/public'
import type { BookingOptionGroup, BootstrapData } from '../services/types'

let bootstrapCache: BootstrapData | null = null
let bootstrapPromise: Promise<BootstrapData> | null = null
let optionCache: BookingOptionGroup[] | null = null
let optionPromise: Promise<BookingOptionGroup[]> | null = null

export async function getBootstrap(force = false): Promise<BootstrapData> {
  if (bootstrapCache && !force) return bootstrapCache
  if (bootstrapPromise && !force) return bootstrapPromise
  bootstrapPromise = fetchBootstrap().then((data) => {
    bootstrapCache = data
    return data
  })
  try {
    return await bootstrapPromise
  } finally {
    bootstrapPromise = null
  }
}

export async function getBookingOptions(force = false): Promise<BookingOptionGroup[]> {
  if (optionCache && !force) return optionCache
  if (optionPromise && !force) return optionPromise
  optionPromise = fetchBookingOptions().then((data) => {
    optionCache = data.groups
    return data.groups
  })
  try {
    return await optionPromise
  } finally {
    optionPromise = null
  }
}

export function clearPublicCaches(): void {
  bootstrapCache = null
  optionCache = null
}
