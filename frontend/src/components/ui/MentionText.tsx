import type { ReactNode } from 'react';
import type { CommentMention } from '../../types';

const MENTION_PATTERN = /@([A-Za-z0-9][A-Za-z0-9._-]*)/g;

/**
 * Build a lowercase handle -> mention map. `mentioned_username` (the handle
 * as typed) is preferred, falling back to the account username.
 */
const buildMentionMap = (mentions?: CommentMention[] | null) => {
  const map = new Map<string, CommentMention>();
  if (!mentions) return map;
  for (const mention of mentions) {
    const handle = (mention.mentioned_username ?? mention.username ?? '').toLowerCase();
    if (handle) map.set(handle, mention);
  }
  return map;
};

/**
 * Renders comment text, turning @handles into links to the referenced
 * account when the mention was resolved (registered on the same platform).
 * Unresolved handles are rendered as plain text.
 */
export const MentionText = ({
  text,
  mentions,
  className,
}: {
  text: string;
  mentions?: CommentMention[] | null;
  className?: string;
}) => {
  const mentionMap = buildMentionMap(mentions);
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  const pattern = new RegExp(MENTION_PATTERN.source, 'g');

  while ((match = pattern.exec(text)) !== null) {
    const handle = match[1].replace(/[._-]+$/, '');
    const mention = handle ? mentionMap.get(handle.toLowerCase()) : undefined;

    // Not a resolved mention: keep scanning, plain text is added below
    if (!mention) continue;

    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <a
        key={`${match.index}-${mention.account_id}`}
        href={`/comments?account_id=${mention.account_id}`}
        className="text-mistral-blue hover:text-mistral-red-deep transition-colors duration-200"
        title={`Referenced account: ${mention.display_name || mention.username || mention.account_id}`}
      >
        {`@${match[1]}`}
      </a>
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return <span className={className}>{parts}</span>;
};
