import type { NavigateFunction } from 'react-router-dom';
import { destinations, type Destination } from './navigation';

export const intentDestinations = {
  movements: 'movements',
  requests: 'requests',
  report: 'requests',
  cards: 'cards',
} as const satisfies Record<string, Destination>;

export type RoutedIntent = keyof typeof intentDestinations;

export function isRoutedIntent(intent: string): intent is RoutedIntent {
  return Object.hasOwn(intentDestinations, intent);
}

export async function navigateForIntent(
  intent: string,
  navigate: NavigateFunction,
  onError: (error: unknown) => void,
): Promise<boolean> {
  try {
    if (!isRoutedIntent(intent)) throw new Error(`Unsupported navigation intent: ${intent}`);
    await navigate(destinations[intentDestinations[intent]]);
    return true;
  } catch (error) {
    onError(error);
    return false;
  }
}
