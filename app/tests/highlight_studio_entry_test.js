const fs=require('fs'),assert=require('assert/strict');
const ui=fs.readFileSync('app/ks/event_clip_ui.py','utf8');
assert(ui.includes('สร้างไฮไลต์พร้อมตกแต่ง'),'highlight must expose the decorated clip route');
assert(ui.includes("ksSide?.('clilab'"),'route must open the existing AI clip workspace');
assert(!ui.includes("promptSelect.value='highlight'"),'opening the workspace must not reset another draft');
console.log('Highlight entry uses existing AI clip workspace without resetting its draft');
