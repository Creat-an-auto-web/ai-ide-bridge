import { BridgeClient, BridgeClientOptions } from './client.js'
import { BridgeSidebarController } from './examples/sidebar-controller.js'
import {
  VoidBridgeController,
  createVoidBridgeContextSource,
} from './examples/void-source-skeleton.js'
import {
  CreateVoidHostServicesOptions,
  createVoidHostServicesFromServices,
} from './void-services-adapter.js'

export interface CreateVoidBridgeRuntimeOptions extends CreateVoidHostServicesOptions {
  bridgeClient?: BridgeClient
  bridgeClientOptions?: BridgeClientOptions
}

const toBridgeClient = (
  options: Pick<CreateVoidBridgeRuntimeOptions, 'bridgeClient' | 'bridgeClientOptions'>,
): BridgeClient => options.bridgeClient ?? new BridgeClient(options.bridgeClientOptions)

export const createVoidBridgeControllerFromServices = (
  options: CreateVoidBridgeRuntimeOptions,
): VoidBridgeController => {
  const client = toBridgeClient(options)
  const hostServices = createVoidHostServicesFromServices(options)
  const contextSource = createVoidBridgeContextSource(hostServices)
  return new VoidBridgeController(client, contextSource)
}

export const createVoidBridgeSidebarControllerFromServices = (
  options: CreateVoidBridgeRuntimeOptions,
): BridgeSidebarController => {
  const client = toBridgeClient(options)
  const hostServices = createVoidHostServicesFromServices(options)
  const contextSource = createVoidBridgeContextSource(hostServices)

  return new BridgeSidebarController({
    bridgeClient: client,
    contextSource,
  })
}
