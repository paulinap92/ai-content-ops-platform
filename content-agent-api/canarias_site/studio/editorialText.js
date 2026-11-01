// Deliberately small Markdown subset. Raw HTML is always escaped.
const escape = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
function inline(value) {
    return escape(value)
        .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
        .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
}
export function renderEditorialText(value) {
    const output = []; let paragraph = [], list = false;
    const flush = () => { if (paragraph.length) {output.push(`<p>${paragraph.map(inline).join("<br>")}</p>`);paragraph=[];} };
    const endList = () => { if (list) {output.push("</ul>");list=false;} };
    for (const line of String(value ?? "").replace(/\r\n?/g,"\n").split("\n")) {
        const heading = /^(#{1,3})\s+(.+)$/.exec(line), bullet = /^[-*]\s+(.+)$/.exec(line);
        if (heading) {flush();endList();const level=heading[1].length+1;output.push(`<h${level}>${inline(heading[2])}</h${level}>`);}
        else if (bullet) {flush();if(!list){output.push("<ul>");list=true;}output.push(`<li>${inline(bullet[1])}</li>`);}
        else if (!line.trim()) {flush();endList();}
        else {endList();paragraph.push(line);}
    }
    flush();endList();return output.join("\n");
}
