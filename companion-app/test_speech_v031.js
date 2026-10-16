'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/app.js','utf8'),stop={hidden:true},synth={cancelCount:0,cancel(){this.cancelCount++;},speak(u){this.last=u;}},context=vm.createContext({window:{speechSynthesis:synth},speechSynthesis:synth,SpeechSynthesisUtterance:class{constructor(text){this.text=text;}},$:()=>stop,error:()=>{}});
vm.runInContext(source.slice(source.indexOf('function stopReadAloud'),source.indexOf('async function exportData')),context);
const button={textContent:'',setAttribute(){}};context.button=button;
vm.runInContext("readAloud('测试',button)",context);assert.equal(button.textContent,'■ 停止朗读');assert.equal(stop.hidden,false);const first=synth.last;
vm.runInContext("readAloud('测试',button)",context);assert.equal(button.textContent,'▷ 朗读');assert.equal(stop.hidden,true);
vm.runInContext("readAloud('新句子',button)",context);first.onend();assert.equal(stop.hidden,false,'old utterance ending cannot reset the new one');vm.runInContext('stopReadAloud()',context);assert.equal(stop.hidden,true);
console.log('Speech toggle, global stop and stale event checks passed.');
