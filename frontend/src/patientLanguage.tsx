import { useSyncExternalStore } from "react";
import { useApp } from "./store";

export type PatientLanguage = "en" | "bn";
const storageKey = "mededge-patient-language";
const eventName = "mededge-language";
let memoryPreference: PatientLanguage | undefined;
function preference(): PatientLanguage {
  if (memoryPreference) return memoryPreference;
  try { const saved = localStorage.getItem(storageKey); if (saved === "en" || saved === "bn") return saved; } catch { /* private browsing */ }
  return navigator.language.startsWith("bn") ? "bn" : "en";
}
function subscribe(callback: () => void) {
  const onStorage = () => { memoryPreference = undefined; callback(); };
  window.addEventListener(eventName, callback); window.addEventListener("storage", onStorage);
  return () => { window.removeEventListener(eventName, callback); window.removeEventListener("storage", onStorage); };
}

// Interface text only. Never translate names, transcripts or clinical evidence here.
const bn = {
  "My health": "আমার স্বাস্থ্য", "Your health information": "আপনার স্বাস্থ্য তথ্য",
  "My records": "আমার রিপোর্ট", "My doctors": "আমার ডাক্তার", "My summary": "আমার সারাংশ",
  "Add a report": "রিপোর্ট যোগ করুন", "Your reports": "আপনার রিপোর্ট", "Choose a report to open it.": "দেখতে চাইলে রিপোর্টটি খুলুন।",
  "Refresh": "আবার দেখুন", "Find a report": "রিপোর্ট খুঁজুন", "Search your records": "রিপোর্টের নাম লিখুন",
  "Filter reports": "রিপোর্ট বাছাই", "Type": "ধরন", "Status": "অবস্থা", "All types": "সব ধরনের",
  "All statuses": "সব অবস্থার", "Prescription": "প্রেসক্রিপশন", "Lab report": "পরীক্ষার রিপোর্ট", "Mixed": "মিশ্র", "Other": "অন্যান্য",
  "Ready for review": "ডাক্তার দেখবেন", "Approved": "যাচাই করা হয়েছে", "Failed": "আবার চেষ্টা করুন", "Interrupted": "মাঝপথে থেমেছে",
  "Show archived reports": "সরিয়ে রাখা রিপোর্ট দেখান", "Detailed history": "বিস্তারিত ইতিহাস", "Loading records…": "রিপোর্ট আসছে…",
  "No archived records": "সরিয়ে রাখা রিপোর্ট নেই", "No records found": "কোনো রিপোর্ট পাওয়া যায়নি",
  "Upload a report or adjust your search to get started.": "রিপোর্ট যোগ করুন অথবা খোঁজার শর্ত বদলান।",
  "Medical report": "স্বাস্থ্য রিপোর্ট", "Doctor’s note ready": "ডাক্তারের নোট এসেছে", "Not yet checked by a doctor": "ডাক্তার এখনো যাচাই করেননি",
  "Record title": "রিপোর্টের নাম", "Save": "সেভ করুন", "Cancel": "বাতিল", "Rename": "নাম বদলান", "Archive": "সরিয়ে রাখুন",
  "Restore": "ফিরিয়ে আনুন", "Delete": "মুছে ফেলুন", "Manage": "পরিবর্তন", "Open report": "রিপোর্ট খুলুন", "Open record": "রিপোর্ট খুলুন",
  "Previous": "আগের পাতা", "Next": "পরের পাতা", "Page": "পাতা", "Clear filters": "সব শর্ত মুছুন",
  "You decide which doctors can see your reports.": "কোন ডাক্তার আপনার রিপোর্ট দেখবেন, তা আপনি ঠিক করবেন।",
  "Check for requests": "নতুন অনুরোধ দেখুন", "Share with a doctor": "ডাক্তারকে দেখার অনুমতি দিন",
  "ONE-TIME CODE · VALID FOR 20 MINUTES": "একবার ব্যবহার করা যাবে · মেয়াদ ২০ মিনিট",
  "Give this code to your doctor. They can request access, but cannot see your chart until you approve.": "কোডটি আপনার ডাক্তারকে দিন। তিনি অনুরোধ পাঠাবেন। আপনি অনুমতি না দেওয়া পর্যন্ত আপনার তথ্য দেখতে পারবেন না।",
  "No connections yet": "এখনো কোনো ডাক্তার যুক্ত নেই", "Create a code when you’re ready to connect with a doctor.": "ডাক্তারকে যুক্ত করতে একটি কোড তৈরি করুন।",
  "Doctor": "ডাক্তার", "Can see your reports": "আপনার রিপোর্ট দেখতে পারেন", "Wants to see your reports": "আপনার রিপোর্ট দেখার অনুমতি চান",
  "Cannot see your reports": "আপনার রিপোর্ট দেখতে পারেন না", "Doctor details": "ডাক্তারের পরিচয়",
  "Professional qualifications have not been checked by MedEdge.": "MedEdge এই ডাক্তারের পেশাগত যোগ্যতা যাচাই করেনি।",
  "I understand what this doctor can see and do.": "এই ডাক্তার কী দেখতে ও করতে পারবেন, তা আমি বুঝেছি।",
  "Allow this doctor": "এই ডাক্তারকে অনুমতি দিন", "Do not allow": "অনুমতি দেবেন না", "Stop sharing": "অনুমতি বন্ধ করুন",
  "Recent changes": "সাম্প্রতিক পরিবর্তন", "Changes to your reports and doctor access.": "রিপোর্ট ও ডাক্তারকে দেওয়া অনুমতির পরিবর্তন।",
  "No activity yet": "এখনো কোনো পরিবর্তন নেই", "Changes to your chart will appear here.": "আপনার তথ্যের পরিবর্তন এখানে দেখা যাবে।",
  "Show fewer changes": "কম দেখুন", "Show older changes": "আগের পরিবর্তন দেখুন", "Your record was updated": "আপনার রিপোর্ট বদলানো হয়েছে",
  "Doctor requested access": "ডাক্তার অনুমতি চেয়েছেন", "Doctor access approved": "ডাক্তারকে অনুমতি দেওয়া হয়েছে",
  "Doctor request declined": "ডাক্তারের অনুরোধ ফিরিয়ে দেওয়া হয়েছে", "Doctor access ended": "ডাক্তারের অনুমতি বন্ধ হয়েছে",
  "Record updated": "রিপোর্ট বদলানো হয়েছে", "Record deleted": "রিপোর্ট মুছে ফেলা হয়েছে", "Doctor published a note": "ডাক্তার নোট দিয়েছেন",
  "Your health summary": "আপনার স্বাস্থ্যের সারাংশ", "Updating your summary…": "আপনার সারাংশ আসছে…",
  "Your health summary will appear after your doctor reviews and publishes a note.": "ডাক্তার যাচাই করে নোট দিলে এখানে আপনার স্বাস্থ্যের সারাংশ দেখা যাবে।",
  "Your summary is unavailable right now. You can still read your notes in detailed history.": "এখন সারাংশ দেখা যাচ্ছে না। বিস্তারিত ইতিহাসে ডাক্তারের নোট পড়তে পারবেন।",
  "Try summary again": "সারাংশ আবার আনুন", "Try again": "আবার চেষ্টা করুন", "Back to my summary": "আমার সারাংশে ফিরুন",
  "Medicines I take now": "এখন যে ওষুধ খাই", "Add a medicine": "ওষুধ যোগ করুন",
  "Keep this list up to date so your doctor knows what you take.": "আপনি এখন কী ওষুধ খান, তা এই তালিকায় রাখুন। এতে ডাক্তার জানতে পারবেন।",
  "Confirmed by you": "আপনি জানিয়েছেন", "Edit": "বদলান", "Remove from list": "তালিকা থেকে সরান",
  "You haven’t added any medicines yet.": "আপনি এখনো কোনো ওষুধ যোগ করেননি।",
  "Medicine name and strength": "ওষুধের নাম ও শক্তি", "Copy the name on the medicine pack": "ওষুধের প্যাকেট দেখে নাম লিখুন",
  "How you take it (optional)": "যেভাবে খান (না লিখলেও চলবে)", "As written on your prescription": "প্রেসক্রিপশনে যেভাবে লেখা আছে",
  "Saving…": "সেভ হচ্ছে…", "Save medicine changes": "ওষুধের পরিবর্তন সেভ করুন", "I take this medicine": "আমি এই ওষুধ খাই",
  "Loading medicines…": "ওষুধের তালিকা আসছে…", "Reload list": "তালিকা আবার আনুন", "Help me find the medicine": "ওষুধের নাম খুঁজতে সাহায্য করুন",
  "Find a Bangladesh medicine": "বাংলাদেশের ওষুধ খুঁজুন", "Brand name, for example Napa": "ব্র্যান্ডের নাম, যেমন Napa", "Search": "খুঁজুন", "Searching…": "খোঁজা হচ্ছে…",
  "Search by the brand on the pack. Check the strength and form; similar names can be different medicines.": "প্যাকেটের ব্র্যান্ডের নাম দিয়ে খুঁজুন। শক্তি ও ধরন মিলিয়ে নিন। কাছাকাছি নামের ওষুধ আলাদা হতে পারে।",
  "Searching the DGHS medicine reference…": "DGHS-এর ওষুধের তালিকায় খোঁজা হচ্ছে…", "Choose": "বেছে নিন", "Reference details": "তথ্যের উৎস",
  "Listed in Bangladesh reference": "বাংলাদেশের ওষুধের তালিকায় আছে", "More results": "আরও ফলাফল", "Previous results": "আগের ফলাফল",
  "No matching product names found. Try the exact brand or enter it manually.": "এই নামে ওষুধ পাওয়া যায়নি। সঠিক ব্র্যান্ড লিখুন অথবা নিজে নাম লিখুন।",
  "Showing a saved reference. Updates could not be checked right now.": "আগের সংরক্ষিত তালিকা দেখানো হচ্ছে। এখন নতুন তথ্য যাচাই করা যায়নি।",
  "You can still enter the medicine manually.": "আপনি নিজেও ওষুধের নাম লিখতে পারবেন।",
  "Your report": "আপনার রিপোর্ট", "Doctor note published": "ডাক্তারের নোট এসেছে", "Upload a clear photo of your prescription or report.": "প্রেসক্রিপশন বা রিপোর্টের পরিষ্কার ছবি দিন।",
  "Refresh status": "অবস্থা আবার দেখুন", "Keep your report in one place": "রিপোর্ট এখানে রাখুন",
  "A sharp, well-lit photo gives the best reading. Include the whole page.": "আলোতে পরিষ্কার ছবি তুলুন। পুরো পাতাটি যেন দেখা যায়।", "Report image": "রিপোর্টের ছবি",
  "Your image is stored until you delete the record. Meta prepares a privacy preview first. You will review it before the redacted page is read.": "রিপোর্ট মুছে না ফেলা পর্যন্ত ছবিটি রাখা হবে। Meta প্রথমে ব্যক্তিগত তথ্য ঢাকার নমুনা তৈরি করবে। আপনি দেখে অনুমতি দিলে ঢাকা ছবিটি পড়া হবে।",
  "Preparing and uploading your report…": "আপনার রিপোর্ট প্রস্তুত ও আপলোড হচ্ছে…", "Explore fictional samples": "কাল্পনিক উদাহরণ দেখুন", "Opening your report…": "আপনার রিপোর্ট খোলা হচ্ছে…",
  "Processing did not finish. Return to My records and add the report again.": "কাজটি শেষ হয়নি। আমার রিপোর্টে ফিরে রিপোর্টটি আবার যোগ করুন।",
  "Preparing your report. You can return to My records and reopen it later.": "রিপোর্ট প্রস্তুত হচ্ছে। আমার রিপোর্টে ফিরে পরে এটি খুলতে পারবেন।",
  "Doctor's notes": "ডাক্তারের নোট", "Report reading": "রিপোর্ট থেকে পড়া তথ্য", "Image & recording": "ছবি ও রেকর্ডিং",
  "Check the privacy preview": "ব্যক্তিগত তথ্য ঢাকা হয়েছে কি না দেখুন", "Saved report image": "রিপোর্টের ছবি",
  "The source preview is unavailable. Saved readings and notes are still available.": "ছবির নমুনা দেখা যাচ্ছে না। সেভ করা তথ্য ও নোট পড়তে পারবেন।",
  "Retry image": "ছবি আবার আনুন", "Report with private regions marked in red": "লাল রঙে ব্যক্তিগত তথ্য চিহ্নিত রিপোর্ট", "Redacted report": "ব্যক্তিগত তথ্য ঢাকা রিপোর্ট",
  "Before processing": "পড়া শুরু করার আগে", "Red marks hidden details. Make sure names, phone numbers and other identifiers are covered. Green marks the area to be read.": "লাল অংশের তথ্য ঢাকা থাকবে। নাম, ফোন নম্বর ও পরিচয় বোঝায় এমন তথ্য ঢাকা আছে কি না দেখুন। সবুজ অংশ পড়া হবে।",
  "Confirm privacy & continue": "তথ্য ঢাকা আছে, এগিয়ে যান", "Original files": "আসল ফাইল", "Download original image": "আসল ছবি নামান", "Doctor's recording": "ডাক্তারের রেকর্ডিং",
  "No original files available for this record.": "এই রিপোর্টের আসল ফাইল পাওয়া যাচ্ছে না।",
  "Recorded reading of a fictional sample.": "কাল্পনিক উদাহরণের আগে থেকে পড়া তথ্য।", "Provisional AI reading. Handwriting may be misread or missing; check the source with your doctor.": "AI-এর পড়া তথ্য এখনো যাচাই করা হয়নি। হাতের লেখা ভুল পড়তে বা বাদ যেতে পারে। ডাক্তারের সঙ্গে আসল রিপোর্ট মিলিয়ে নিন।",
  "Medicines as written": "লেখা অনুযায়ী ওষুধ", "No medicines extracted.": "ওষুধ পড়া যায়নি।", "Test results": "পরীক্ষার ফলাফল", "Name": "নাম", "Value": "ফল", "Unit": "একক", "Range": "স্বাভাবিক সীমা",
  "Not recorded": "লেখা নেই", "No test results extracted.": "পরীক্ষার ফল পড়া যায়নি।", "Tests as written": "লেখা অনুযায়ী পরীক্ষা", "No reading available. Check the original report.": "পড়া তথ্য পাওয়া যাচ্ছে না। আসল রিপোর্ট দেখুন।",
  "Your doctor's notes": "আপনার ডাক্তারের নোট", "Reviewed and published by your connected doctor.": "আপনার ডাক্তার যাচাই করে দিয়েছেন।", "Print or save as PDF": "প্রিন্ট করুন বা PDF রাখুন",
  "Patient": "রোগী", "Updated note": "সংশোধিত নোট", "No published note yet. Your image reading remains provisional until reviewed by a doctor.": "ডাক্তার এখনো নোট দেননি। ডাক্তার যাচাই না করা পর্যন্ত ছবির পড়া তথ্য নিশ্চিত নয়।",
  "Manage doctor access": "ডাক্তারের অনুমতি দেখুন", "Preparing preview": "নমুনা তৈরি হচ্ছে", "Check privacy": "তথ্য ঢাকা হয়েছে কি না দেখুন", "Processing": "কাজ চলছে", "Ready to review": "যাচাইয়ের জন্য প্রস্তুত", "Reviewed": "যাচাই করা হয়েছে", "Needs retry": "আবার চেষ্টা করুন",
  "Patient portal": "রোগীর পাতা", "Account": "অ্যাকাউন্ট", "Sign out": "সাইন আউট", "Signing out…": "সাইন আউট হচ্ছে…", "Use light mode": "হালকা রং ব্যবহার করুন", "Use dark mode": "গাঢ় রং ব্যবহার করুন",
  "Stop sharing your reports with {name}?": "{name}-কে রিপোর্ট দেখার অনুমতি বন্ধ করবেন?",
  "Permanently delete “{title}” and its notes? This cannot be undone.": "“{title}” ও এর নোট চিরতরে মুছবেন? এটি ফেরত আনা যাবে না।",
  "Remove {name} from your current-medicines list? This changes your list only, not your prescription.": "এখন খাওয়া ওষুধের তালিকা থেকে {name} সরাবেন? শুধু তালিকা বদলাবে, প্রেসক্রিপশন নয়।",
  "Leave without saving your medicine changes?": "ওষুধের পরিবর্তন সেভ না করে চলে যাবেন?", "Discard the medicine changes you have not saved?": "সেভ না করা ওষুধের পরিবর্তন বাদ দেবেন?",
  "Reload and discard unsaved medicine changes?": "সেভ না করা পরিবর্তন বাদ দিয়ে তালিকা আবার আনবেন?",
  "Something went wrong. Please try again.": "কাজটি করা যায়নি। আবার চেষ্টা করুন।",
  "Could not load your records.": "রিপোর্ট আনা যায়নি। আবার চেষ্টা করুন।", "Could not load your care team.": "ডাক্তারদের তথ্য আনা যায়নি। আবার চেষ্টা করুন।",
  "The service is starting or unavailable. Please try again in a moment.": "সেবা চালু হচ্ছে অথবা এখন পাওয়া যাচ্ছে না। একটু পরে আবার চেষ্টা করুন।",
  "Could not save the medicine.": "ওষুধ সেভ করা যায়নি। আবার চেষ্টা করুন।", "Could not update the list.": "তালিকা বদলানো যায়নি। আবার চেষ্টা করুন।",
  "This image could not be prepared. Choose another photo.": "ছবিটি প্রস্তুত করা যায়নি। অন্য ছবি দিন।", "The upload failed. Please try again.": "আপলোড হয়নি। আবার চেষ্টা করুন।",
  "All saved history, including archived reports. Updated from the latest saved entries.": "সরিয়ে রাখা রিপোর্টসহ এখানে আপনার সেভ করা বিস্তারিত ইতিহাস আছে।",
  "Loading the full history…": "বিস্তারিত ইতিহাস আসছে…",
  "Read your doctor’s notes": "ডাক্তারের নোট পড়ুন",
  "Open your reports": "আপনার রিপোর্ট খুলুন",
  "No doctor-published assessment yet. Unreviewed readings are listed below.": "ডাক্তার এখনো নোট দেননি। নিচের পড়া তথ্য এখনো যাচাই করা হয়নি।",
  "Report readings — not checked by a doctor": "রিপোর্ট থেকে পড়া তথ্য — ডাক্তার যাচাই করেননি",
  "Medicines mentioned": "রিপোর্টে লেখা ওষুধ",
  "As extracted from dated reports; these may be inaccurate or no longer current.": "পুরোনো রিপোর্ট থেকে পড়া তথ্য ভুল হতে পারে। এগুলো এখন খাওয়া ওষুধের তালিকা নয়।",
  "Tests & results": "পরীক্ষা ও ফলাফল",
  "Provisional readings and tests advised in saved reports.": "সেভ করা রিপোর্টের পরীক্ষা ও ফলাফল এখনো যাচাই করা হয়নি।",
  "No tests or results extracted.": "পরীক্ষা বা ফলাফল পড়া যায়নি।",
  "No reports have been saved yet.": "এখনো কোনো রিপোর্ট সেভ করা হয়নি।",
  "Archived": "সরিয়ে রাখা",
  "Published": "ডাক্তার দিয়েছেন",
  "Advised": "করতে বলা হয়েছে",
  "Account changed": "অ্যাকাউন্ট বদলেছে",
  "Checking your session…": "আপনার অ্যাকাউন্ট যাচাই হচ্ছে…",
  "Please sign in again": "আবার সাইন ইন করুন",
  "We couldn’t check your session": "আপনার অ্যাকাউন্ট যাচাই করা যায়নি",
  "Check account again": "অ্যাকাউন্ট আবার যাচাই করুন",
  "Open sign in in a new tab": "নতুন ট্যাবে সাইন ইন খুলুন",
  "Check your connection, then try again. Your work stays in this tab while it remains open.": "ইন্টারনেট সংযোগ দেখে আবার চেষ্টা করুন। এই ট্যাব খোলা থাকলে আপনার কাজ এখানে থাকবে।",
  "This tab is paused to protect your work. Sign in to the original account in another tab, then return here. Unsaved edits remain in this tab while it stays open.": "আপনার কাজ নিরাপদ রাখতে এই ট্যাব থামানো হয়েছে। অন্য ট্যাবে আগের অ্যাকাউন্টে সাইন ইন করে এখানে ফিরুন। এই ট্যাব খোলা থাকলে সেভ না করা কাজ এখানে থাকবে।",
  "Could not check stored files. Please retry.": "সেভ করা ফাইল দেখা যায়নি। আবার চেষ্টা করুন।",
  "Could not create a connection code. Try again.": "কোড তৈরি হয়নি। আবার চেষ্টা করুন।",
  "Review the current consent before approving.": "অনুমতি দেওয়ার আগে শর্তগুলো আবার পড়ুন।",
  "Request not found.": "অনুরোধটি আর পাওয়া যাচ্ছে না। নতুন অনুরোধ দেখুন।",
  "Connection not found.": "ডাক্তারের সংযোগটি পাওয়া যাচ্ছে না। আবার তালিকা দেখুন।",
  "Chart not found.": "এই স্বাস্থ্য তথ্য পাওয়া যাচ্ছে না অথবা দেখার অনুমতি নেই।",
  "Record not found.": "রিপোর্টটি পাওয়া যাচ্ছে না অথবা দেখার অনুমতি নেই।",
  "Unknown run": "রিপোর্টটি পাওয়া যাচ্ছে না অথবা দেখার অনুমতি নেই।",
  "Enter a title.": "রিপোর্টের নাম লিখুন।",
  "Wait for processing to finish before deleting this record.": "কাজ শেষ হলে রিপোর্টটি মুছতে পারবেন।",
  "Could not delete stored files. Try again.": "সেভ করা ফাইল মুছতে পারিনি। আবার চেষ্টা করুন।",
  "Shared demo accounts cannot change consent.": "কাল্পনিক ডেমো অ্যাকাউন্টে অনুমতি বদলানো যায় না।",
  "Shared demo accounts accept the fictional samples only.": "ডেমো অ্যাকাউন্টে শুধু কাল্পনিক উদাহরণ ব্যবহার করুন।",
  "The image exceeds the 12 MB limit.": "ছবিটি ১২ MB-এর বেশি। ছোট ছবি দিন।",
  "The service is busy. Please retry shortly.": "সেবা ব্যস্ত। একটু পরে আবার চেষ্টা করুন।",
  "Permanent file storage is not configured.": "ফাইল রাখার সেবা এখন প্রস্তুত নয়। পরে আবার চেষ্টা করুন।",
  "Could not save the uploaded files. Please retry.": "আপলোড করা ফাইল সেভ করা যায়নি। আবার চেষ্টা করুন।",
  "This run is not waiting for confirmation": "এই রিপোর্টে এখন নিশ্চিত করার প্রয়োজন নেই। অবস্থা আবার দেখুন।",
  "File unavailable": "ফাইলটি পাওয়া যাচ্ছে না।",
  "File not ready": "ফাইলটি এখনো প্রস্তুত হয়নি। একটু পরে দেখুন।",
  "Could not load your doctor's notes. Refresh to try again.": "ডাক্তারের নোট আনা যায়নি। আবার দেখুন।",
  "Confirmation failed": "নিশ্চিত করা যায়নি। আবার চেষ্টা করুন।",
  "Your active account changed.": "অন্য অ্যাকাউন্টে সাইন ইন করা হয়েছে। আগের অ্যাকাউন্টে ফিরে আসুন।",
  "Could not load the patient overview.": "স্বাস্থ্য তথ্য আনা যায়নি। আবার চেষ্টা করুন।",
  "This medicine changed elsewhere. Reload the list before editing.": "অন্য জায়গায় এই ওষুধের তথ্য বদলেছে। বদলানোর আগে তালিকা আবার আনুন।",
  "Medicine not found.": "ওষুধটি তালিকায় পাওয়া যাচ্ছে না। তালিকা আবার আনুন।",
  "Enter the medicine name.": "ওষুধের নাম লিখুন।",
  "Please try adding the medicine again.": "ওষুধটি আবার যোগ করার চেষ্টা করুন।",
  "This request was already saved with different details.": "এই অনুরোধে অন্য তথ্য সেভ হয়েছে। তালিকা আবার দেখুন।",
  "This request was already saved. Refresh your list.": "তথ্যটি সেভ হয়েছে। তালিকা আবার দেখুন।",
  "Choose a photo": "ছবি বেছে নিন",
  "Refine the brand name to narrow these results.": "ফলাফল কমাতে ব্র্যান্ডের নাম আরও নির্দিষ্ট করে লিখুন।",
  "Registry entry": "তালিকার তথ্য",
  "DGDA registration data, curated by DGHS. Checked {date}. A registry listing does not confirm pharmacy stock. Generic-name searches may miss branded products.": "DGHS-এর সাজানো DGDA নিবন্ধনের তথ্য। যাচাইয়ের তারিখ {date}। তালিকায় নাম থাকা মানেই দোকানে ওষুধ আছে নয়। জেনেরিক নাম দিয়ে খুঁজলে কিছু ব্র্যান্ড বাদ পড়তে পারে।",
} as const;
export type PatientText = keyof typeof bn;
export function translatePatient(text: string, language: PatientLanguage): string { return language === "bn" && text in bn ? bn[text as PatientText] : text; }
export function usePatientLanguage() {
  const selected = useSyncExternalStore(subscribe, preference, () => "en" as const);
  const role = useApp(state => state.user?.role);
  const language = role === "patient" ? selected : "en";
  return {
    language, locale: language === "bn" ? "bn-BD" : "en-GB",
    t: (text: PatientText) => translatePatient(text, language),
    message: (text: string | null | undefined) => translatePatient(text || "", language),
    format: (text: PatientText, values: Record<string, string>) => Object.entries(values).reduce((result, [key, value]) => result.replaceAll(`{${key}}`, value), translatePatient(text, language)),
  };
}
export function PatientLanguageControl() {
  const { language } = usePatientLanguage();
  return <div className="segmented patient-language" role="group" aria-label="Language / ভাষা">
    {(["en", "bn"] as const).map(value => <button key={value} type="button" lang={value} aria-pressed={language === value} onClick={() => {
      memoryPreference = value;
      try { localStorage.setItem(storageKey, value); } catch { /* preference is optional */ }
      window.dispatchEvent(new Event(eventName));
    }}>{value === "en" ? "English" : "বাংলা"}</button>)}
  </div>;
}
