import React from 'react';

const paragraphStyle = {
  fontSize: 14,
  color: 'var(--color-text-secondary)',
  lineHeight: 1.75,
  margin: 0,
};

function renderInline(text) {
  const parts = String(text || '').split(/(\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={index} style={{ color: 'var(--color-text-primary)', fontWeight: 650 }}>
          {part.slice(2, -2)}
        </strong>
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

function FormattedText({ text, accentColor = 'var(--color-text-success)' }) {
  const blocks = splitBlocks(text);

  if (!blocks.length) {
    return null;
  }

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      {blocks.map((block, index) => {
        const bulletItems = getBulletItems(block);

        if (isHeading(block)) {
          return (
            <p
              key={index}
              style={{
                fontSize: 12,
                fontWeight: 700,
                color: 'var(--color-text-primary)',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                margin: 0,
              }}
            >
              {cleanHeading(block)}
            </p>
          );
        }

        if (bulletItems) {
          return (
            <div key={index} style={{ display: 'grid', gap: 10 }}>
              {bulletItems.map((item, itemIndex) => (
                <div key={itemIndex} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: '50%',
                      background: accentColor,
                      marginTop: 9,
                      flexShrink: 0,
                    }}
                  />
                  <p style={paragraphStyle}>{renderInline(item)}</p>
                </div>
              ))}
            </div>
          );
        }

        return (
          <p key={index} style={paragraphStyle}>
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
