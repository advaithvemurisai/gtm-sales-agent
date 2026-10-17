import React from 'react';

// Older saved results joined cited fragments with spaces ("led it ." / "( PitchBook"); close those gaps.
function tidySpacing(text) {
  return String(text || '')
    .replace(/[ \t]+([.,;:!?)\]])/g, '$1')
    .replace(/([(\[])[ \t]+/g, '$1');
}

function renderInline(text) {
  const parts = tidySpacing(text).split(/(\*\*[^*]+\*\*)/g);

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

function splitRow(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());
}

// A markdown table: a header row, a |---|---| separator, then body rows.
function getTable(block) {
  const lines = block.split('\n').map((line) => line.trim()).filter(Boolean);
  if (lines.length < 2 || !lines.every((line) => line.startsWith('|'))) return null;
  if (!/^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$/.test(lines[1])) return null;
  return { header: splitRow(lines[0]), rows: lines.slice(2).map(splitRow) };
}

function FormattedText({ text }) {
  const blocks = splitBlocks(text);
  if (!blocks.length) return null;

  return (
    <div className="prose">
      {blocks.map((block, index) => {
        if (isHeading(block)) return <p key={index} className="prose-heading">{cleanHeading(block)}</p>;

        const table = getTable(block);
        if (table) {
          return (
            <div key={index} className="prose-table-wrap">
              <table className="prose-table">
                <thead>
                  <tr>{table.header.map((cell, cellIndex) => <th key={cellIndex} scope="col">{renderInline(cell)}</th>)}</tr>
                </thead>
                <tbody>
                  {table.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex}>{renderInline(cell)}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

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
