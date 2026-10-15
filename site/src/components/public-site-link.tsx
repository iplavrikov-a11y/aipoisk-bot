'use client';

import type { AnchorHTMLAttributes } from 'react';
import { usePublicSiteContacts } from '@/lib/public-site-settings';

type Props = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> & { channel: 'bot' | 'telegram' | 'email' };

export function PublicSiteLink({ channel, children, ...props }: Props) {
  const { contacts, bot } = usePublicSiteContacts();
  const href = channel === 'bot' ? bot.telegram_url : channel === 'telegram' ? contacts.telegram_url : `mailto:${contacts.email}`;
  const label = channel === 'bot' ? bot.telegram : channel === 'telegram' ? contacts.telegram : contacts.email;
  return <a {...props} href={href}>{children ?? label}</a>;
}
