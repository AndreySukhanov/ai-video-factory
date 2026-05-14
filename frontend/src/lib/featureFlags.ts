const TRUE_VALUES = new Set(["1", "true", "yes", "on"]);

function isTrue(value: string | undefined): boolean {
  if (!value) return false;
  return TRUE_VALUES.has(value.trim().toLowerCase());
}

const rawUiV2 = process.env.NEXT_PUBLIC_UI_V2;

// Default is enabled for internal rollout; set NEXT_PUBLIC_UI_V2=0 to fallback to legacy page.
export const isUiV2Enabled = rawUiV2 === undefined ? true : isTrue(rawUiV2);
