export type Lang = 'english' | 'hinglish' | 'hindi';

export const STRINGS: Record<string, Record<Lang, string>> = {
  'persona.label': {
    english: 'Persona',
    hinglish: 'Persona',
    hindi: 'भूमिका',
  },
  'persona.ED': {
    english: 'Executive Director',
    hinglish: 'Executive Director',
    hindi: 'कार्यकारी निदेशक',
  },
  'persona.ASSET_MANAGER': {
    english: 'Asset Manager / PE',
    hinglish: 'Asset Manager / PE',
    hindi: 'एसेट मैनेजर / पीई',
  },
  'persona.FIELD_ENGINEER': {
    english: 'Field Engineer',
    hinglish: 'Field Engineer',
    hindi: 'फ़ील्ड इंजीनियर',
  },
  'persona.demo_note': {
    english: 'Demo persona switch — not a security boundary',
    hinglish: 'Demo persona switch hai — security boundary nahi',
    hindi: 'डेमो भूमिका स्विच — सुरक्षा सीमा नहीं',
  },
  'rbac.not_permitted': {
    english: 'Not permitted for your role',
    hinglish: 'Aapke role ke liye allowed nahi',
    hindi: 'आपकी भूमिका के लिए अनुमति नहीं',
  },
  'rbac.hidden_tab': {
    english: 'Hidden for this persona',
    hinglish: 'Is persona ke liye hidden',
    hindi: 'इस भूमिका के लिए छिपा',
  },
  'map.synthetic': {
    english: 'Synthetic coordinates (demo)',
    hinglish: 'Synthetic coordinates (demo)',
    hindi: 'कृत्रिम निर्देशांक (डेमो)',
  },
  'map.all_fields': {
    english: 'All fields',
    hinglish: 'Saare fields',
    hindi: 'सभी फ़ील्ड',
  },
  // v0.6 ED-9 (D-38): three display tags — Healthy / Needs attention / Not producing
  'map.health.PRODUCING_OK': {
    english: 'Healthy',
    hinglish: 'Healthy',
    hindi: 'स्वस्थ',
  },
  'map.health.ATTENTION': {
    english: 'Needs attention',
    hinglish: 'Dhyan chahiye',
    hindi: 'ध्यान चाहिए',
  },
  'map.health.AT_RISK': {
    english: 'Needs attention',
    hinglish: 'Dhyan chahiye',
    hindi: 'ध्यान चाहिए',
  },
  'map.health.UNDERPERFORMING': {
    english: 'Needs attention',
    hinglish: 'Dhyan chahiye',
    hindi: 'ध्यान चाहिए',
  },
  'map.health.NOT_PRODUCING': {
    english: 'Not producing',
    hinglish: 'Band / not producing',
    hindi: 'उत्पादन बंद',
  },
  'map.cluster_hint': {
    english: 'Zoom in to expand clusters',
    hinglish: 'Cluster kholne ke liye zoom karein',
    hindi: 'क्लस्टर खोलने के लिए ज़ूम करें',
  },
  'map.wells': {
    english: 'wells',
    hinglish: 'wells',
    hindi: 'कुएँ',
  },
};

export function t(key: string, lang: Lang = 'english'): string {
  return STRINGS[key]?.[lang] ?? STRINGS[key]?.english ?? key;
}
