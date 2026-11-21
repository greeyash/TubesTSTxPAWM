import { Platform } from 'react-native';

export const colors = {
  skyTop: '#C9DFF5',
  skyMid: '#E4EFFA',
  bg: '#F3F7FB',
  card: '#FFFFFF',
  text: '#14212E',
  muted: '#6B7A8A',
  border: '#E4EBF2',
  blue: '#3A7BC8',
  blueSoft: '#E3EEFA',
  dark: '#16212C',
  yellow: '#F6C445',
  yellowSoft: '#FDF1CF',
  green: '#2E8A57',
  greenSoft: '#E2F4EA',
  amber: '#B07400',
  amberSoft: '#FCEFD3',
  red: '#C0392B',
  redSoft: '#FBE5E2',
  // dipertahankan untuk kompatibilitas komponen lama
  primary: '#3A7BC8',
  primarySoft: '#E3EEFA',
};

export const space = (n) => n * 4;
export const radius = 20;

export const shadow = Platform.select({
  web: { boxShadow: '0 6px 18px rgba(20, 33, 46, 0.08)' },
  default: { shadowColor: '#14212E', shadowOpacity: 0.08, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 3 },
});

// ilustrasi per kategori (pengganti foto)
export const CATEGORY_ART = {
  outdoor: { colors: ['#B8E8D2', '#5FB88E'], icon: 'leaf' },
  indoor: { colors: ['#CDD6FF', '#7D8DEB'], icon: 'business' },
  landmark: { colors: ['#FFDDB0', '#EE9B4D'], icon: 'flag' },
  kuliner: { colors: ['#FFD0CC', '#EC7F74'], icon: 'restaurant' },
};
