import React from 'react';

function renderInline(text) {
  const parts = String(text || '').split(/(\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={index}>{part.slice(2, -2)}</strong>
      );
    }

    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

export function InlineFormattedText({ text }) {
  return <>{renderInline(text)}</>;
}

function splitBlocks(text) {
  return String(text || '')
    .replace(/\r\n/g, '\n')
    // Raw search text can carry markdown headings; render them as the bold heading blocks below.
    .replace(/^#{1,6}\s+(.+)$/gm, '\n\n**$1**\n\n')
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);
}

function cleanHeading(block) {
  return block.replace(/^\*\*(.+?)\*\*:?\s*$/, '$1').trim();
}

function isHeading(block) {
  return /^\*\*.+?\*\*:?\s*$/.test(block);
}

function getBulletItems(block) {
  const lines = block.split('\n').map((line) => line.trim()).filter(Boolean);
  if (!lines.length || !lines.every((line) => /^[-*]\s+/.test(line))) {
    return null;
  }

  return lines.map((line) => line.replace(/^[-*]\s+/, '').trim()).filter(Boolean);
}

function FormattedText({ text }) {
  const blocks = splitBlocks(text);
  if (!blocks.length) return null;

  return (
    <div className="prose">
      {blocks.map((block, index) => {
        if (isHeading(block)) return <p key={index} className="prose-heading">{cleanHeading(block)}</p>;

        const bulletItems = getBulletItems(block);
        if (bulletItems) {
          return (
            <ul key={index} className="prose-list">
              {bulletItems.map((item, itemIndex) => <li key={itemIndex}>{renderInline(item)}</li>)}
            </ul>
          );
        }

        return (
          <p key={index}>
            {block.split('\n').map((line, lineIndex) => (
              <React.Fragment key={lineIndex}>
                {lineIndex > 0 && <br />}
                {renderInline(line)}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}

export default FormattedText;
