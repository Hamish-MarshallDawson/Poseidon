# Flags and prediction: next steps (team conversation)

Transcript of `Flag and predicition next steps.m4a` (6.5 minutes), recorded on the night of 7 to 8 November 2026. It was transcribed with Whisper large-v3, run locally on Hamish's desktop, so the audio never left the team. The text is as spoken. Two notes on it:

- "MRI" in the audio almost certainly means **AIS**.
- Whisper repeated one phrase at about 2:56; it is cut back to once below and marked.

## What was decided (summary)

**1. Gap detection, which defines a "dark vessel"**
- **Scope:** Class A vessels only, using AISStream alone. Satellite data plays no part in detection.
- **Candidate:** a vessel whose last ping is **more than 30 minutes** old.
- **Dark vessel:** a candidate whose grid square was busy while it was silent. Busy means **at least 10 other vessels pinged in that square in the last 20 minutes**, which rules out a ship that has simply gone out of range in open water. All thresholds can be tuned once the detector runs on live data.
- **Duration:** the status holds **until the vessel pings again, or expires after 24 hours**.
- **Wording:** the system never says a ship *is* a dark vessel, only that the possibility is high. Going dark may or may not be on purpose.

**2. Other flags to add**
- **Name change:** rare, but easy to add and worth having.
- **Rendezvous:** two vessels (not dark ones) **close together, at slow speed, in open water**, which can indicate a transfer or trafficking.
- More flags can follow once these work.

**3. Prediction (still open: what is the target?)**
- **Option A, risk:** score every ship for how likely it is to go dark soon, based on its behaviour.
- **Option B, path:** learn from history where ships go during AIS gaps.
  - Match historical AIS tracks to the delayed satellite radar detections (GFW and Sentinel-1 arrive days late) to rebuild the path through each gap.
  - Train on that, then predict a ship's path from **live AIS alone**.
  - The pitch: it saves the cost of live, paid satellite tasking, by building the framework around satellite imagery without needing it in real time.
- **The question raised at the end:** what exactly is the regression target? The working answer is the ship's position or path during a gap, learned from AIS matched to radar.

**4. Approach**
- Get the basic detectors working first as a baseline, then add more on top.

## Transcript

**[0:00]** So we're focusing on class A vessels right? For the gap. For the gap detection. So if you, so we find its last ping, if its last ping was more than 30 minutes ago, it's a candidate for the gap detection. Now if you left it there, it could just be that the vessel was gone off into open water. But what we do is the square that it's in, if it's had sufficient activity, which I'm defining as, I think it's 10 vessels, this can all be changed. If 10 vessels have reported, have pinged in the square in the last 20 minutes. Oh but that one hasn't. But this one hasn't, then that's a dark vessel. Okay. And it starts a gap. Yeah. Right. So this will start a gap and if it's longer than that it will be determined to dark vessel. Yeah. And then it will hold that like

**[1:00]** dark vessel status until it pings again. Yeah. Or it will be, or after 24 hours that dark vessel status will expire. Okay. That's the way I'm thinking about it right now. Is this independent of satellite or MRI pings or is this specifically the MRI pings? This is just AIS stream I think. AIS stream, MRI, okay. Yeah. Okay. Yeah. So that's like the gap analysis which then defines what a dark vessel is. And that can be used for a little bit of magic? Yeah, yeah. legal fishing it can be used for a bunch of stuff right like yeah in theory it can apply to in theory this a dark vessel is one that needs attention a bad actor it appears that they might be trying to hide something yeah it could be it could be a false flag they could have

**[1:46]** so we've got a dark vessel detection system it's cooking okay so and obviously i'm going to tune this depending on when we plug it into live there we'll see because there might be no dark vessels i think what we need to remember is that we're not we're not directly saying they are dark vessels the possibility of them being a dark vessel is high right if they're going dark it could be on purpose yeah it is not on purpose it could be on purpose yeah the other things the other things we need to flag in general okay the we haven't touched prediction yet but that's fine the other things we need to flag are a name change yeah that usually doesn't happen though that's yeah it's still good to have it's still good to have

**[2:35]** okay um because quite easy maybe um we need to flag uh i would love to do the rendezvous thing yeah i think maybe we're all clear on that but maybe the recording is not clear but the rendezvous uh the rendezvous detection is essentially detecting two vessels that are not dark vessels *[Whisper repeated this phrase many times; probably said once]* which are close together at slow speed in open water because there's potential that they're like trafficking something so those two things would be interesting to get into um then i think maybe there's more flags that would be cool but then we want a prediction right so this is what i'm concerned about because i don't know a prediction would be i don't know what we're what we're trying to predict so right now obviously

**[3:27]** we have the detection when it happens yeah the prediction if we're doing a dark vessel prediction pure dark vessel prediction would be saying looking at all the ships in the water and saying this one has quite a high likelihood of going dark soon or something like that well that that can be one of the predictions based on its behavior one of the predictions could just be the pathing because we'll have historical data for the ais stream like mri signals that the boats themselves send as well as the satellite things that get that hit those ships while they're not able to send those pinks because they're in open waters so we'll have historical data that allows us to see and look at the mri pings and how they relate to the satellite pings and then since the satellite things we get now aren't live because they're you know we don't have access to those

**[4:13]** like full paid super expensive satellite systems but we get like a few days later the only live data we have like you know properly live within like a few minutes of what is actually happening is the like mri asi stream stuff yeah so if we're able to look at the history of the retrain how the asio and the satellites interact and how that shows the pathing if we're able to predict where a ship is going to go with just the asi stream or the si the ais stream without the predictions without these expensive satellites and data and that can save money and stuff like that yeah and that's that's that's your problem solving right there not only are you flagging

**[4:59]** them up on the on the prediction model you're saving them the cost of having to run the satellites to do that yeah right so sorry because the boomer is going to see it as right we have satellite imagery let's slap it into our ai model and get it to check for itself right we're basically building the framework around that that's right good it's going to be sick it's going to be sick we can always ask we can always do some research if we get some of these basic ones done first get the system in place then we can add more as we go remember we've got the baseline yeah we take this as a baseline we make these work and then we add on top so hang on just on that bit you were talking about what is what is the target attribute what are you trying to regress a value what are you trying to find out so i mean when we're looking at the historical data we'll see the full track that a vessel took we'll see each mmri ping that it sends throughout the

**[5:48]** entire process so throughout the coast where it's in line and you can send those we'll have all of that and then once it stops sending those potentially a dark vessel or it just doesn't have the signal in the open waters we're able to match those mri signals to the radar pings that get sent in historical data from the satellites so then looking at that we're able to trace the path that this boat took even though we're missing the mri pings in between so then the idea is that once we have trained the model enough without the satellite live data that we don't have access to we're still able to look at the mri pings and figure out where it's going to go now your agent it's asking for the gaps though
