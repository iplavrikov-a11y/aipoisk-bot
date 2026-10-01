'use client';

import { createContext, useContext, type ReactNode } from 'react';
import type { PublicSitePayload } from './site-data';

type PublicContacts = Pick<PublicSitePayload, 'contacts' | 'bot'>;
const PublicContactsContext = createContext<PublicContacts | null>(null);

export function PublicSiteSettingsProvider({ settings, children }: { settings: PublicContacts; children: ReactNode }) {
  return <PublicContactsContext.Provider value={settings}>{children}</PublicContactsContext.Provider>;
}

export function usePublicSiteContacts() {
  const settings = useContext(PublicContactsContext);
  if (!settings) throw new Error('Public site settings provider is missing');
  return settings;
}
