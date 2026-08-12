// Client-side country/state validation for the Customer and Supplier forms.
// Mirrors backend app/utils/location_validation.py so the same rules are enforced
// before the request is sent (the backend remains the source of truth).
//
//   * Country -> must be a recognised country name; continents and unknown
//     tokens are rejected.
//   * State   -> free-form region, but must NOT be a country or continent name.
//
// The list of valid countries is passed in from the customization-options
// endpoint (which returns the full country master), so we don't duplicate it.

const CONTINENTS = new Set([
  'asia',
  'africa',
  'europe',
  'north america',
  'south america',
  'central america',
  'latin america',
  'antarctica',
  'oceania',
  'australia and oceania',
  'americas',
  'eurasia',
  'middle east',
  'sub-saharan africa',
  'caribbean',
  'scandinavia',
]);

// Common shorthands users type -> canonical master name.
const COUNTRY_ALIASES: Record<string, string> = {
  usa: 'United States',
  'u.s.a.': 'United States',
  us: 'United States',
  'u.s.': 'United States',
  'united states of america': 'United States',
  america: 'United States',
  uk: 'United Kingdom',
  'u.k.': 'United Kingdom',
  'great britain': 'United Kingdom',
  britain: 'United Kingdom',
  england: 'United Kingdom',
  uae: 'United Arab Emirates',
  'u.a.e.': 'United Arab Emirates',
  korea: 'South Korea',
  'czech republic': 'Czechia',
};

const clean = (value?: string | null): string => (value || '').trim().replace(/\s+/g, ' ');

/** Return the canonical country name for `value`, or null if unrecognised. */
export const canonicalCountry = (value: string | null | undefined, countries: string[]): string | null => {
  const token = clean(value).toLowerCase();
  if (!token) return null;
  const match = countries.find((c) => c.toLowerCase() === token);
  if (match) return match;
  if (COUNTRY_ALIASES[token]) return COUNTRY_ALIASES[token];
  return null;
};

/** Return an error message if the country is invalid, else null. */
export const validateCountryValue = (
  value: string | null | undefined,
  countries: string[],
  label = 'Country',
): string | null => {
  const token = clean(value);
  if (!token) return null; // optional
  if (CONTINENTS.has(token.toLowerCase())) {
    return `${label} must be a valid country, not a continent ("${token}" is a continent)`;
  }
  if (!canonicalCountry(token, countries)) {
    return `"${token}" is not a valid country name. Please enter a valid ${label.toLowerCase()}.`;
  }
  return null;
};

/** Return an error message if the state is a country/continent name, else null. */
export const validateStateValue = (
  value: string | null | undefined,
  countries: string[],
  label = 'State',
): string | null => {
  const token = clean(value);
  if (!token) return null; // optional
  if (CONTINENTS.has(token.toLowerCase())) {
    return `${label} must be a state/region, not a continent ("${token}" is a continent)`;
  }
  if (canonicalCountry(token, countries)) {
    return `${label} must be a state/region, not a country ("${token}" is a country)`;
  }
  return null;
};
