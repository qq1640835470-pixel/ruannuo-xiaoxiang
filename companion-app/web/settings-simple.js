'use strict';
(()=>{
const sections=[...document.querySelectorAll('.drawer-body > .settings-section')];
for(const section of sections.slice(1)){const heading=section.querySelector('h3');if(!heading)continue;const group=document.createElement('details'),summary=document.createElement('summary');group.className='settings-group';summary.textContent=heading.textContent;section.before(group);group.append(summary,section);}
})();
