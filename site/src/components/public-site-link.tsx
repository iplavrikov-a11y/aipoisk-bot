'use client';

import type { AnchorHTMLAttributes } from 'react';
import { usePublicSiteContacts } from '@/lib/public-site-settings';

type Props = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> & { channel: 'bot' | 'telegram' | 'email' | 'phone' };

export function PublicSiteLink({ channel, children, ...props }: Props) {
  const { contacts, bot } = usePublicSiteContacts();
  const href =
    channel === 'bot'
      ? bot.telegram_url
      : channel === 'telegram'
      ? contacts.telegram_url
      : channel === 'phone'
      ? contacts.phone_url || 'tel:+79210629909'
      : `mailto:${contacts.email}`;
  const label =
    channel === 'bot'
      ? bot.telegram
      : channel === 'telegram'
      ? contacts.telegram
      : channel === 'phone'
      ? contacts.phone || '+7 (921) 062-99-09'
      : contacts.email;
  return <a {...props} href={href}>{children ?? label}</a>;
}
