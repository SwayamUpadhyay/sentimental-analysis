import pandas as pd
import random

products = [
    'Asus ROG Strix G16',
    'Lenovo Legion Pro 5i',
    'Razer Blade 16',
    'Acer Predator Helios 16',
    'Dell Alienware m16 R2'
]

# Generate 60 reviews per product spanning diverse sentiment categories.
data = {
    'Asus ROG Strix G16': [
        # Highly Positive
        'Absolutely blown away by the Strix G16. The i9 and 4080 combo crushes Cyberpunk 2077 on max settings without breaking a sweat.',
        'This is the best laptop I have ever owned. The Nebula display is incredibly vibrant and the refresh rate makes everything buttery smooth.',
        'Incredible desktop replacement. I do heavy 3D rendering in Blender all day and it absolutely flies through exports.',
        'The build quality is phenomenal this year! Very sturdy chassis, minimal deck flex, and the thermals are remarkably stable under load.',
        '10/10 machine. Asus nailed the cooling system with the third fan design. I can barely hear it while gaming at 1440p.',
        'Zero complaints. Got it on sale, battery life on Optimus is actually solid for web browsing, and the RGB is stunning.',
        'Perfect gaming laptop. The keyboard is so tactile and comfortable for long sessions, and the Wi-Fi 6E is rock solid.',
        'I am absolutely loving the liquid metal factory application. Getting 120fps in Starfield on high settings!',
        'This laptop is a beast. Everything feels premium, from the trackpad click to the subtle rubberized coating on the deck.',
        'Incredible value for the performance you get. It outperforms laptops that cost $500 more. Very happy with my purchase.',
        
        # Positive
        'Very solid laptop for the price. Fast, reliable, and handles my Steam library well. Armory Crate is a bit clunky though.',
        'Great screen and really nice keyboard. It gets a bit warm near the top vents but nothing alarming.',
        'Solid buy. Performance is exactly what I expected from the specs. The speakers are pretty good too for a laptop.',
        'I like it a lot. Battery life is decent if you lower the brightness and turn off the RGB. Good for college and gaming.',
        'Very happy overall. The display brightness is good enough for a lit room and the contrast is surprisingly good for IPS.',
        'Good machine. Took a little tweaking to get the fan curves right, but now it runs quiet and fast.',
        'I upgraded the RAM and SSD very easily. The internals are well laid out and easy to access. Good job Asus.',
        'Plays everything flawlessly at 1080p and mostly handles 1440p well too. Very satisfied.',
        'Nice design, not too gamery if you turn the lights off. Fits in at the office but plays AAA titles at home.',
        'I recommend it. Just uninstall McAffee immediately and update all the Asus drivers from the website, not Windows Update.',
        
        # Neutral
        'It is an okay laptop. Performance is fine, but it is quite bulky and the battery life is average.',
        'Does the job. It plays games okay, but the screen could be a bit brighter and the fans are definitely noticeable.',
        'A very middle-of-the-road experience. Nothing amazing, nothing terrible. You get what you pay for.',
        'Specs are exactly as advertised. It runs well, though I wish it had an SD card reader or one more USB port.',
        'It works fine as a desktop replacement. I wouldn’t want to carry this around in a backpack every day though.',
        'Performance is good, but the software overhead takes a lot of RAM. Standard gaming laptop stuff.',
        'Just average build quality. All plastic, feels a bit cheap compared to a Razer, but it also costs less.',
        'The webcam is 720p and barely functional in low light. The rest of the laptop is fine.',
        'It is decent. I had to do a fresh install of Windows to get rid of the manufacturer bloatware to make it run smoothly.',
        'Fine for gaming, but typing on it for work all day gets tiring because the front edge is a bit sharp.',
        
        # Negative
        'Disappointed with the coil whine. It makes a high-pitched buzzing noise whenever the GPU is under load.',
        'The battery life is atrocious. I get maybe 2 hours just typing a Word document on battery saving mode.',
        'Armory Crate software is terrible. It keeps forgetting my lighting profiles and uses too much CPU in the background.',
        'Trackpad is loose and rattles when you tap it. For this price, I expect better quality control from Asus.',
        'Runs way too hot. The CPU regularly hits 95 degrees while gaming and the keyboard deck gets uncomfortable to touch.',
        'Wi-Fi keeps dropping randomly during multiplayer games. I updated the drivers and it still happens.',
        'The speakers are very quiet and have absolutely zero bass. My phone sounds better than this.',
        'Not a great buy. The screen backlight bleed in the bottom corners is really distracting during dark movie scenes.',
        'I expected more. The fans sound like a jet engine even on the performance profile, not just turbo.',
        'Asus support is unhelpful. My screen developed a dead pixel and they refuse to fix it under warranty.',
        
        # Highly Negative
        'Absolute garbage. Motherboard completely died after 3 weeks of normal use. Asus RMA process is a nightmare taking months.',
        'Do not buy this! It thermal throttles constantly, making games unplayable after 15 minutes due to massive frame drops.',
        'Worst laptop I have ever owned. Crashes daily with blue screens related to their terrible bundled software.',
        'Terrible quality control. Mine came with a busted hinge right out of the box and Asus blames me for physical damage.',
        'A complete waste of $2000. Constant stuttering in games, audio crackling, and the case gets dangerously hot.',
        'I bitterly regret buying this. The liquid metal leaked and shorted the board. Asus refused to cover it. Avoid!',
        'Horrendous software experience. Updates broke my GPU drivers and now it refuses to detect the Nvidia card at all.',
        'Screen flickers black constantly when switching between integrated and dedicated graphics. Impossible to work or game.',
        'Absolute junk. The fan bearing broke on day 2 and it sounds like a grinding chainsaw. Returning it immediately.',
        'WARNING to buyers: Asus will scam you on repairs. They quoted me $1200 for a microscopic scratch they caused during a fan swap.',
        
        # Sarcastic / Ironic
        'Oh, sure, I definitely wanted a laptop that sounds like a Boeing 747 taking off when I open Chrome.',
        'Battery life is amazing! If by amazing you mean I can make it from the desk to the couch before it dies.',
        'Love the RGB lights. Now I can be blinded while I deal with Armory Crate crashing for the 5th time today.',
        'Coil whine? No, that is just a built-in mosquito deterrent. Thanks Asus!',
        'So glad I paid $2000 for a laptop that is as portable as a cinder block.',
        'The trackpad is huge! Perfect for ignoring because I use a mouse anyway.',
        'Yes, I love repasting my brand new laptop because the factory application looks like it was done by a toddler.',
        'Armory Crate is a masterpiece of software engineering. Said absolutely no one ever.',
        'Who needs a space heater when you have this running Cyberpunk?',
        'Wow, a 720p webcam in 2024. Just what I needed for my professional Zoom calls.'
    ],
    
    'Lenovo Legion Pro 5i': [
        # Highly Positive
        'Absolutely flawless machine. The thermals are unbeatable; CPU stays below 75C even during heavy compiles.',
        'The 16:10 QHD+ 500 nits display is jaw-droppingly gorgeous. Best laptop screen I have ever seen.',
        'Incredible build quality. The aluminum lid feels premium and the hinge is rock solid with no wobble.',
        'Best keyboard on any gaming laptop, period. It has true Lenovo ThinkPad DNA.',
        '100% recommend. Lenovo Vantage is actually useful and not bloated, and it controls the power states perfectly.',
        'Incredible desktop replacement. I get over 140 FPS in Warzone at 1440p.',
        'The I/O is perfect. Having all the major ports on the back spine makes desk cable management a dream.',
        'Flawless out of the box experience. No bloatware, fast setup, incredibly fast SSD.',
        'Super impressed with the battery life on hybrid mode. I can get through a whole 6-hour school day easily.',
        'Worth every single penny. It is quiet, fast, beautiful, and feels extremely durable.',
        
        # Positive
        'Great laptop! Performance is very stable and I love the understated design that does not look too gamery.',
        'Very good screen and fast performance. It handles my video editing workflow seamlessly.',
        'Sturdy build and great typing experience. It is a bit heavy, but you expect that for the cooling performance.',
        'I am quite happy with it. The fans get loud under load, but it never throttles. That is a good trade-off to me.',
        'Solid machine. Lenovo Vantage makes it super easy to switch between quiet and performance modes.',
        'Really good value for money. The 4070 runs cool and the port selection on the back is very convenient.',
        'Everything works perfectly. G-Sync is a game changer for smooth gameplay.',
        'Nice and robust. The chassis is mostly plastic on the bottom but feels very thick and durable.',
        'Takes a bit of tweaking in Vantage to get battery life up, but once you do, it is very reasonable.',
        'Great daily driver for both work and gaming. I just wish the power brick was a little smaller.',
        
        # Neutral
        'It is fine. It does what a gaming laptop should do, but it is quite bulky.',
        'Average experience. The performance is good but the battery drains completely in 3 hours of browsing.',
        'It is a solid performer, but I find the 16:10 screen aspect ratio weird for watching movies (big black bars).',
        'Standard heavy gaming laptop. Works well on a desk, but terrible for actual lap use.',
        'The trackpad is plastic, not glass, which is a bit disappointing for the price, but it works okay.',
        'Performance is exactly in line with the hardware, nothing more, nothing less.',
        'It is okay. I had an issue with the Wi-Fi dropping once but a driver update seemed to fix it.',
        'The lack of Thunderbolt on the AMD version is a bummer, but the speed is fine.',
        'Just a regular thick laptop. Good cooling, but hard to transport daily.',
        'Screen is decent, performance is decent. A very safe, unexciting purchase.',
        
        # Negative
        'My battery drains even when the laptop is plugged into the wall and I am gaming. This is a known design flaw.',
        'The motherboard has terrible coil whine under the keyboard. It is very annoying in quiet rooms.',
        'Lenovo Vantage software randomly updated and now my custom fan curves are broken and gone.',
        'The speakers are extremely poor quality. They sound muffled and pointing downward does not help.',
        'Very disappointed in the realtek Wi-Fi card they use to cut costs. It drops connection constantly on 5GHz.',
        'Heavy and uncomfortable. The sharp front lip digs into my wrists when typing for long periods.',
        'Keyboard flexes a lot in the center. Expected better from a Lenovo branded machine.',
        'Not a fan of the power brick size. It weighs almost as much as the laptop itself.',
        'It gets way hotter than reviews claimed. GPU routinely hits 86C throttle limit for me.',
        'Disappointed with the screen backlight bleed. All four corners glow yellow on dark screens.',
        
        # Highly Negative
        'Motherboard fried after 2 months. Lenovo Premium Warranty is a scam, they have been waiting on parts for 6 weeks.',
        'Terrible machine. It blue screens consistently every time I try to wake it from sleep mode.',
        'Absolute trash QA. My unit arrived with a dead pixel dead center, and support says 1 dead pixel is acceptable.',
        'Do not buy. The hinge snapped under normal use after 6 months and Lenovo claims it is customer induced damage.',
        'Worst experience ever. The laptop randomly shuts off entirely during gaming. Replaced power supply, still happens.',
        'Complete garbage. The internal SSD died and took all my data with it within the first 30 days.',
        'A $1600 paperweight. The BIOS update bricked the motherboard and Lenovo expects me to pay for shipping it to a depot.',
        'Avoid this model! The cooling fans make a high-pitched grinding noise that gives me a headache after 10 minutes.',
        'Horrible stuttering in every game. The CPU is aggressively thermal throttling down to 800MHz.',
        'Lenovo support is atrocious. They hung up on me twice when I tried to claim warranty for a broken trackpad.',
        
        # Sarcastic / Ironic
        'So heavy I use it to anchor my boat.',
        'Vantage software: because I wanted 40 background processes running for no reason.',
        'The hinge wobbles like it owes me money.',
        'Ah, the famous Lenovo battery drain while plugged in. Truly revolutionary design.',
        'Screen is nice, if you like looking at a mirror in a well-lit room.',
        'Love the subtle design. By subtle I mean it looks like a 1990s ThinkPad on steroids.',
        'They put the ports on the back! Revolutionary. Next they will figure out how to cool it.',
        'The power brick weighs more than the laptop. I think it has its own zip code.',
        'Nothing says quality like the trackpad rattling on every click.',
        'I appreciate that it comes with McAfee. I always wanted a digital virus built-in.'
    ],
    
    'Razer Blade 16': [
        # Highly Positive
        'The absolute pinnacle of laptop engineering. The CNC aluminum chassis feels exactly like a black MacBook Pro.',
        'The Mini-LED dual-mode screen is mind-blowing. 4K for content creation and 1080p 240Hz for competitive gaming is genius.',
        'Incredibly thin and incredibly powerful. The vapor chamber cooling manages the i9 and 4090 perfectly.',
        'Nothing else on the market compares to this build quality. Absolutely stunning piece of technology.',
        'Best in class. The massive glass trackpad is flawless and the speakers actually have deep bass.',
        '10/10. Worth the premium price. Synapse actually works well to control the performance profiles.',
        'Extremely fast, gorgeous display showing perfect blacks, and minimal fan noise on balanced mode.',
        'This is the ultimate portable workstation/battlestation. Handles 8K video editing seamlessly.',
        'Flawless perfection. The per-key RGB is the brightest and most customizable I have ever seen.',
        'A breathtaking machine. Compact, sleek, and incredibly powerful. I will never buy another brand.',
        
        # Positive
        'Great laptop! It feels totally premium. Does run a bit warm, but that is expected for this thickness.',
        'Very happy with the dual mode screen. Build quality is top notch and it is very portable.',
        'Solid performance. Fits perfectly in my tech bag and does not look embarrassing in a business meeting.',
        'Love it. The specs are great and the aluminum body is superb. Battery life is decent if you use 60Hz and Optimus.',
        'Very nice machine. The trackpad is the best on any Windows laptop, bar none.',
        'Good purchase. Pricey, but it delivers on the sleek aesthetic and high frame rates.',
        'Impressive thermals for its size. The vapor chamber really puts in work. Keyboard takes getting used to, but overall great.',
        'Screen is beautiful, games run smooth. Just be sure to wipe off fingerprints regularly.',
        'I really like the compact GaN charger they included this generation. Makes traveling much easier.',
        'Very capable laptop. It undervolts well which drops the temps considerably. Happy so far.',
        
        # Neutral
        'It is a stunning laptop, but you are definitely overpaying for the CNC aluminum shell.',
        'Performance is exactly what you expect for a 4080, but I wish the keyboard had more travel.',
        'It is alright. The fans spin up even when just watching YouTube, which is annoying.',
        'Average experience. Looks great, but gets very uncomfortably hot to use actually on your lap.',
        'Overall good, but the battery life is 4 hours max. You carry the charger everywhere.',
        'Pretty decent. The Mini-LED is nice but there is noticeable blooming around bright objects on black backgrounds.',
        'The laptop is fine, but Synapse software is bulky and requires an account login which is dumb.',
        'It runs my games, but $3500 is very steep for what essentially matches a $2000 Asus in raw speed.',
        'Build is great, but the 1080p webcam is very muddy. Average machine otherwise.',
        'A very ‘safe’ premium option. You pay for the logo more than the pure performance.',
        
        # Negative
        'Ridiculously overpriced. It thermal throttles constantly so you never get the full performance of the parts you paid for.',
        'Spicy pillow warning! My battery bloated after 14 months and warped the entire bottom chassis.',
        'Extremely uncomfortable to use. The aluminum body acts as a heatsink and will literally burn your legs.',
        'Razer Synapse is bloatware garbage that constantly crashes and causes blue screens.',
        'Disappointed. The screen backlight strobes at low brightness giving me massive headaches.',
        'The anti-fingerprint coating is a lie. This thing looks greasy 5 seconds after you wipe it down.',
        'Terrible battery life. I am lucky to get 2 hours on battery just browsing the web.',
        'The palm rejection on the massive trackpad is awful. I keep accidentally clicking while typing.',
        'Awful customer support. Trying to get a replacement charger took 4 weeks of emails back and forth.',
        'The fans have a high pitched whine that drives me absolutely crazy in a quiet office.',
        
        # Highly Negative
        'Absolute trash. Motherboard fried 2 days out of warranty. Razer refused to help and quoted $1800 to fix.',
        'Do NOT buy. The battery bloat issue is still here! My trackpad popped out after 8 months because of gas expansion.',
        'Worst $3000 I ever spent. Screen died completely on week two. RMA process is deliberately confusing and slow.',
        'A complete scam. It gets so hot playing simple games that it forces a hard system shutdown to prevent melting.',
        'Appalling quality control. Both of the Type-C ports failed within a month. Laptop is basically useless now.',
        'Terrible. Synapse update bricked my keyboard lighting entirely and Razer support essentially said tough luck.',
        'Garbage machine. Constant micro-stuttering in Windows desktop. It is a known Nvidia Optimus issue they refuse to fix.',
        'I hate this laptop. The speakers crackle and pop loudly every time audio starts or stops.',
        'Avoid at all costs. The chassis warped from heat and now it wobbles on a flat desk. Unacceptable.',
        'Razer Care is a joke. They received my laptop for repair a month ago and have not updated me once.',
        
        # Sarcastic / Ironic
        'Oh great, my battery turned into a spicy pillow. I always wanted an explosive laptop.',
        'I love paying the Razer tax. It makes me feel superior while getting lower FPS than a Lenovo.',
        'It gets so hot you can fry an egg on the deck. Truly a multi-purpose machine.',
        'The fingerprint magnet finish is great. I can see what I ate for lunch three days ago on the lid.',
        'Razer Synapse: the only malware you pay to install.',
        'Ah, the beautiful Mini-LED display. Complete with gorgeous blooming around every white text box.',
        'I sure do love paying $3000 for 16GB of soldered RAM.',
        'The build quality is Mac-like. Which means I am terrified to scratch it.',
        'Fans are whisper quiet! Because thermal throttling kicked in and it gave up.',
        'It is so thin! Too bad the laws of thermodynamics still apply.'
    ],
    
    'Acer Predator Helios 16': [
        # Highly Positive
        'Incredible value for the performance! 4080 GPU at this price is unbeatable. Handles everything maxed out at 1600p.',
        'The new MagKey 3.0 switches are amazing. They actually feel like a mechanical keyboard. Love the tactile click.',
        'Cooling is fantastic on this year’s model. The 5th gen AeroBlade tech genuinely keeps temperatures well below 80C.',
        'Phenomenal screen! The Mini-LED 250 nits display is blindingly bright and colors are perfectly tuned out of the box.',
        '10/10 machine. Acer finally stepped up their game. Build feels sturdy, performance is monstrous, and I love the rear exhaust.',
        'Best gaming laptop I have ever owned. Zero stutter, incredibly fast Gen4 SSD speeds, and Wi-Fi 7 is incredibly fast.',
        'Absolutely destroys 4K video editing and Unity rendering. The CPU/GPU power phasing works perfectly.',
        'Such a massive improvement over older Acers. The software is very intuitive to use for overclocking.',
        'A total powerhouse. Running Cyberpunk with Path Tracing and holding 70fps effortlessly is a dream.',
        'Flawless. Great IO port placement, excellent thermals, and an overall extremely satisfying buy.',
        
        # Positive
        'Great machine overall. The fans are a bit loud on Turbo, but the cooling performance justifies it entirely.',
        'Very solid performance. Good build quality, and the keyboard feels surprisingly nice for long gaming sessions.',
        'Happy with my purchase. Screen is great. Battery is weak, but I leave it plugged in so it doesn’t matter to me.',
        'Solid mid-to-high tier performer. Plays my entire library well and the screen aspect ratio is great for coding.',
        'Really good laptop for the price. Acer Predator software is actually pretty lightweight and useful this time around.',
        'Performance is exactly as advertised. Good fast screen with minimal ghosting. Great for esports.',
        'I like it. Looks a bit gamery but the custom lighting is cool. Runs all my VR games without a hitch.',
        'Good laptop. The swappable WASD keys are a fun gimmick, and the overall cooling is very effective.',
        'Pleased with the performance. Easy to open up and add another strict M.2 SSD. Recommend it!',
        'A great deal compared to Alienware or Razer. You get the exact same frame rates for hundreds less.',
        
        # Neutral
        'It is a decent laptop. Performs well but the design is very aggressive and the chassis is quite thick.',
        'Average gaming machine. Loud under load, heavy in the bag. Gets the job done though.',
        'It runs games fine. The screen backlight is a bit uneven on dark scenes, but I only notice it in dark rooms.',
        'Standard bulky laptop. The PredatorSense button placement is weird, I keep accidentally pressing it.',
        'Hits the frame targets but the fans sound like a drone taking off. Just physics I suppose.',
        'Okay machine. Plastic bottom panel feels cheap, but the aluminum lid is nice. Mixed bag.',
        'Performance is good, but battery life is essentially 2 hours doing light browsing. Needs to stay tethered.',
        'It works. Wi-Fi has been somewhat spotty for me on battery but works fine plugged in.',
        'A very average experience. Nothing particularly innovative, just a solid chassis with good chips stuffed in.',
        'Fine for the price. The trackpad is a bit annoying, slightly too far to the left for my liking.',
        
        # Negative
        'Way too loud. The fans are deafening even on the balanced profile. Had to return it.',
        'Terrible battery life and the battery drains while gaming even when plugged in. Very poor power design.',
        'PredatorSense software is absolute trash. Takes forever to load and fails to apply my RGB changes.',
        'Keyboard flex is really bad on the left side near the WASD cluster. Feels very cheap for a premium tier.',
        'Disappointed with the thermals. CPU hits 98C instantly under load and thermal throttles hard.',
        'The audio is abysmal. Speakers are incredibly weak and distort heavily at over 70% volume.',
        'Too heavy and massive. The power cord is incredibly bulky and short, making it hard to use comfortably.',
        'I absolutely hate the boot-up loud swoosh sound that you can not permanently disable in BIOS.',
        'Trackpad rattles loudly with every tap. This is unacceptable quality control.',
        'Screen ghosting is noticeable in fast-paced games despite the advertised 3ms response time.',
        
        # Highly Negative
        'Absolute garbage. Motherboard failed within 40 days. Acer support is dodging my calls and emails.',
        'Do not buy Acer. My laptop freezes multiple times a day requiring a hard reboot. Completely unusable for work.',
        'Worst thermal design ever. The liquid metal application was botched from the factory, spilling onto resistors.',
        'Complete waste of money. The GPU just disappeared from device manager. Reinstalled Windows, still dead.',
        'Horrendous build. The screen hinge snapped off the chassis just from opening the lid normally.',
        'I deeply regret this purchase. The screen has massive backlight bleed that covers 50% of the display.',
        'Absolute junk. One of the cooling fans died and makes a horrifying grinding noise. Acer wants $200 to assess it.',
        'Do not buy this! It overheated so badly it warped the plastic bottom shell and melted the rubber foot.',
        'Terrible quality. Dead pixels appeared after 2 weeks. Acer said it requires 5 dead pixels to replace the screen.',
        'A total scam. Advertised speeds are completely unachievable due to instant hard throttling. Do not give them your money.',
        
        # Sarcastic / Ironic
        'PredatorSense is clearly named that because it preys on your RAM.',
        'Ah, the Acer ‘gamer aesthetic’. So glad my laptop screams I HAVE NEVER TOUCHED GRASS.',
        'The fans sound like a hair dryer. On high. Right next to my ear.',
        'Turbo mode is just a button to quickly induce hearing loss.',
        'I love how the power plug is placed directly where my hand wants to go.',
        'Build quality is excellent if you like the feel of recycled Tupperware.',
        'Wow, Liquid Metal! Too bad they applied it with a fire hose.',
        'The screen is bright enough to blind me, which is great because it hides the backlight bleed.',
        'Battery life is measured in milliseconds, apparently.',
        'The boot logo sound gives me a heart attack every time.'
    ],
    
    'Dell Alienware m16 R2': [
        # Highly Positive
        'Absolutely incredible redesign! The smaller footprint without the huge rear thermal shelf makes it actually portable now.',
        'The new Stealth Mode hotkey is brilliant. Instantly turns off all RGB and lowers fans for class/meetings.',
        'Phenomenal performance from the Core Ultra chip. Handles all my AI workflows incredibly fast.',
        'Build quality is a 10/10. The anodized aluminum and soft-touch deck feel more premium than almost any other laptop.',
        'Flawless gaming experience. QHD+ 240Hz screen is butter smooth and the G-Sync implementation is perfect.',
        'Best Alienware in years. The thermals are actually fully under control, rarely seeing above 80C under heavy load.',
        'Absolutely love the aesthetics. It looks mature but still retains that classic Alienware sci-fi vibe.',
        'Such an amazing laptop. Keyboard is clicky, responsive, and has the perfect amount of travel.',
        'Incredibly solid. The performance per watt on this chassis is amazing. Great battery life doing non-gaming tasks.',
        'A masterpiece of engineering. The redesigned cooling system is remarkably quiet while still pushing high frames.',
        
        # Positive
        'Great laptop overall. Looks way better than the R1. Performance is excellent for 1440p gaming.',
        'Pretty solid machine. The screen is great and the stealth mode feature is actually very useful for college.',
        'Good build quality. Feels very dense and sturdy. Fans can get loud but performance is top tier.',
        'I am very happy with it. AWCC is a bit buggy, but once you set your colors, the hardware itself is fantastic.',
        'Solid upgrade from my old m15. Love the 16:10 aspect ratio and the slightly improved speaker quality.',
        'Very good performance. Stays reasonably cool for how thin it is now. Highly recommend.',
        'Nice screen, great keyboard. It is a bit heavy but much more manageable than last year’s model.',
        'I really like the new design language. Runs Cyberpunk and Helldivers flawlessly.',
        'Great machine. Boot times are insane and Windows Hello facial recognition works perfectly out of the box.',
        'Pleased with the battery life for a gaming laptop. Solid 6 hours for light web browsing.',
        
        # Neutral
        'It is decent. The redesign is nice, but it feels like they compromised slightly on raw cooling power to get it smaller.',
        'Average gaming laptop. The screen is 300 nits, which is fine for indoors but bad if you sit near a bright window.',
        'Works fine. I miss the rear I/O shelf because now all cables stick out the sides and get in the way of my mouse.',
        'It is an okay performer. Definitely overpaying for the Alienware logo, but it runs well enough.',
        'The laptop itself is good, but the Command Center software is still very slow and clunky.',
        'Standard performance. Good build, but nothing really blows you away for the price they ask.',
        'Decent machine, but the trackpad is still surprisingly small for a 16-inch laptop in 2024.',
        'Just fine. Stealth mode is mostly a gimmick, you could just manually do it with a macro.',
        'Performance is average for a 4070. The fans have a slightly weird pitch but you get used to it.',
        'Good, not great. I expected slightly better thermals. It runs warm on the keyboard deck.',
        
        # Negative
        'Severely disappointed in the Core Ultra CPU performance. It gets beaten by last year’s 13th gen chips in gaming.',
        'AWCC software is completely broken. It uses 15% of my CPU at all times just running in the background.',
        'The fans never truly turn off, even in quiet mode while doing nothing. Always a low hum.',
        'Very dim screen! For this much money, a 300-nit display is an absolute joke. Looks washed out.',
        'Trackpad is unresponsive sometimes after waking from sleep. Need to reboot to fix it.',
        'Overpriced for the performance you get. Lenovo gives you the identical specs for $400 less.',
        'The removal of the rear cooling shelf made it run much hotter. My unit hits 100C constantly and throttles.',
        'Alienware Support is terrible. They remote into my PC, update drivers, and close the ticket without fixing the hardware issue.',
        'Speakers are awful. Zero bass and they sound tinny. Very disappointing for a premium brand.',
        'The soft-touch coating on the palm rest wears off and gets incredibly oily looking after just 2 weeks of use.',
        
        # Highly Negative
        'Absolute trash. Motherboard died within hours of unboxing. Quality control at Dell has completely disappeared.',
        'A complete scam of a laptop. The GPU wattage is artificially limited so it performs 20% worse than competitors.',
        'Worst purchase ever. Constant BSODs related to Dell SupportAssist software. Unusable out of the box.',
        'Do not buy! The fans sound like a whining drill and the left speaker blew out on day 3 at half volume.',
        'Horrible thermals. It gets so hot playing Minecraft that it physically burns the tips of my fingers on the WASD keys.',
        'I absolutely hate this laptop. It randomly disconnects from Wi-Fi and drops my Bluetooth mouse constantly.',
        'Complete junk. The hinge is so loose the screen falls backward if you tilt the laptop even slightly.',
        'Dell warranty is a nightmare. They dragged out replacing my defective screen for 3 months until I threatened a chargeback.',
        'Terrible screen tearing and stuttering. Optimus almost never switches correctly. Avoid this generation entirely.',
        'A $2000 brick. A mandatory Dell BIOS update failed and corrupted the board. They refuse to cover it under warranty.',
        
        # Sarcastic / Ironic
        'Oh wow, they removed the rear tail. Now it just looks like a regular overpriced Dell.',
        'Alienware Command Center. The final boss of all bloatware.',
        'I love how my ‘Stealth Mode’ just means the fans are slightly less deafening.',
        'Great laptop! Only had to reinstall Windows three times to get the RGB working.',
        'The power adapter isn’t a brick, it’s a paving stone.',
        'Battery life is incredible. It lasts a whole hour!',
        'I enjoy how the palm rest gets warm. Saves me money on heating.',
        'Nothing says ‘Premium’ like the plasticky creak when I open the lid.',
        'Wow, Core Ultra! Very cool. Still throttles like a 10th gen.',
        'I love how Dell support just remote-installs SupportAssist and calls it a day.'
    ]
}

# Mix the sentiments so they are not grouped together.
# We have 6 categories of 10 reviews each.
for product in data:
    reviews = data[product]
    
    highly_pos = reviews[0:10]
    pos = reviews[10:20]
    neutral = reviews[20:30]
    neg = reviews[30:40]
    highly_neg = reviews[40:50]
    sarcastic = reviews[50:60]
    
    mixed = []
    for i in range(10):
        # Pick one from each category for this batch of 6
        batch = [
            highly_pos[i],
            pos[i],
            neutral[i],
            neg[i],
            highly_neg[i],
            sarcastic[i]
        ]
        # Shuffle the batch so the pattern isn't exactly the same every time
        random.shuffle(batch)
        mixed.extend(batch)
        
    data[product] = mixed

df = pd.DataFrame(data)
df.to_csv('test_reviews.csv', index=False)
