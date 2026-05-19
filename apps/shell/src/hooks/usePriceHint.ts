/**
 * usePriceHint — fetch an item's poe.ninja price by name.
 *
 * Backs the `<PriceBadge>` shown on gear cells. TanStack-Query cached
 * (15 min) and only fires when `itemName` is non-null — callers pass
 * `null` for items that can't be name-priced (rares).
 */

import { useQuery } from "@tanstack/react-query";
import { getQuote } from "../api/pricing";

export interface PriceHint {
  /** Chaos-orb value, or null when unpriced / still loading. */
  chaos: number | null;
  /** Divine-orb value, or null when poe.ninja didn't report one. */
  divine: number | null;
  loading: boolean;
}

export function usePriceHint(itemName: string | null): PriceHint {
  const query = useQuery({
    queryKey: ["price-quote", itemName],
    queryFn: () => getQuote(itemName as string),
    enabled: !!itemName,
    staleTime: 15 * 60 * 1000,
  });
  return {
    chaos: query.data?.quote?.chaos_value ?? null,
    divine: query.data?.quote?.divine_value ?? null,
    loading: !!itemName && query.isLoading,
  };
}
