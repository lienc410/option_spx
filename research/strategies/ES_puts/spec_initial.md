Strategy #1 - Long VTI

Background: I am a traditional 100% buy/hold SP500 investor so I always want to maintain good exposure to the market while using the collateral for option-based strategies.

The Trade: Buy VTI equivalent to 70% of NLV (target 70/30 VTI/cash).

Timing: Now. Don't try and time the market.

Management: Re-invest premiums from theta plays and/or cash deposits at the end of every month to maintain desired exposure.

Notes: Having a core long position helps to prevent FOMO on the inevitable hulky green days.

Example: Position as of 12/28/24

Strategy #2 - /ES Puts

Background: I switched to /ES from SPX in July of 2021 (see comparison and reasoning here) and use a very similar strategy which is detailed in my 2021 Recap Post (minus the short calls).

The Trade: Write 21/28/35/42/49 DTE puts at ~20 delta. Number of contracts scales with account size. I also give myself some wiggle room on delta but if you start going single digits there, you better know what you are doing. I used to have a target yield with these and kept it very mechanical (i.e. 4 contracts at 5 delta and 45 DTE every Wednesday) but I just don't believe that's optimal if you have the time/experience I do now.

Timing: This is the tricky part and most important change I've made to my core strategy that has led to enhanced results. In a clear uptrend or immediately after any type of de-risking/bullish event (think post-election or after 8/5 this year), I'm willing to add short /ES puts right up to my max leverage rules in the table below. Like most of my trading, I like to scale in assuming I have enough room (this might look like adding 1 contract each of 21/28/35/42/49 DTE a couple different days per week for my NLV). In a downtrend/pull-back, I'm basically just sitting tight with current positions and only managing if I start breaking leverage rules. This change has allowed me to capture more premium in a bull market (which is where we spend most of our time) while theoretically keeping the same P/L in a bear market.

Management: I will close any short put for a loss if <-300% and only look to re-open if I'm within my leverage rules. If these are getting tested near expiration, I will close for whatever gain/loss at the time to avoid gamma risk. Taking profits is not a mechanical process anymore for me. I rarely let anything go to expiry but, if we are in a clear uptrend and well within my leverage limits, I'll let positions run to even +90% before closing. On the other end, I'll happily take +50% if approaching a binary event like NVDA earnings/FOMC/etc. and I'm feeling apprehensive. And as I'm reducing leverage by taking profits, I'm usually opening up at-least a small portion at the same time (kind of like rolling up for a credit).

Notes: Spintwig has taught us that SPY 45 DTE short calls are not profitable long-term (the 5 delta are almost breakeven). Resist the urge to make these a core part of a mechanical strategy (take it from someone who has had to learn this lesson too many times totaling 6-figures in lifetime losses). If you must add this high risk/low reward negative delta, keep a strict stop-loss (I use to use -500%).

Example: Position as of 12/28/14

Strategy #3 - Long /ES Calls (Testing/Learning in Smaller PM Account)

Background: Ideally, I'd like to have leveraged market exposure via long calls (instead of any short /ES puts or vega exposure) when VIX is sub-15 so I have max BP to deploy when vol explodes. So, the idea would be to maintain the same P/L as strategy #2 via long calls and use short /ES puts as additional plays on those +30% VIX days. My lifetime experience in eating -500% losses on long-term ES short calls and some recent huge hits on ES long calls this year has led me to try this fun experiment.

The Trade: Purchase 21/45/60/90/120 DTE long /ES calls at 10-15 delta. Not sure on sizing but I am thinking of starting with a max allocation of 0.5% per week. This way, max loss would be 26% but assuming I could break even on half and hit a few homeruns in there, hoping I could limit the damage to mid-single digits loss for the year.

Timing: Only open these when in an uptrend or appear to be bouncing into one (IV crush out of a VIX spike can crush long calls more than one might think). Not sure how often but I like the idea of averaging down on the longer-term calls when I can.

Management: This is the tough part I have with negative theta plays vs. positive ones - knowing when to take profit. I like the idea of immediately setting a GTC order at 100% profit for half the order to make the position free and then going from there. I'm also wondering how looking at the SPY B-delta of the long calls can help me manage (curious how much the delta accelerates in a melt-up). I'm going to be testing a lot here.

Notes: Like everything else for me, this will certainly be a trial by fire (aka losing money 😅) but one worth exploring regardless of the outcome.

Note that I do of-course dabble in many other trades such as individual equity ratios (my favorite thing to do), earnings trades (not worth it), day-trading futures (I suck), day-trading NVDA (I suck), etc. but the bulk of my gains comes from strategy #1 and #2 above.

****************

Leverage

SPY B-Delta (Spy Portfolio Beta-Weighted Delta)

Calculation: Your SPY B-delta tells you how you move relative to SPY. Your NLV/SPY tells you how many SPY shares you can buy. If you divide your SPY B-delta by this number, that will tell you your leverage w/ respect to SPY. For most of us options traders, this number is a snapshot in time as it will dynamically move as the market and volatility moves. Regardless, it gives you a good idea of how exposed you are.

Background: I use the table below pretty strictly to keep my leverage from getting out of hand. The whole idea is to prevent a margin call and forced liquidations during a massive volatility event. In fact, these are exactly the type of scenarios thetagangers dream of opening positions in. So, the numbers below are also intended to leave ample room for selling more premium during such occasions.

Management: If I'm over the boundaries, I almost always cut. However, if I'm failing but also calling bullshit because of panic-induced fear, I'll buy short-dated NTM puts until I fall back within the guidelines (I actually had some of these on during the 12/18 meltdown because I was slightly over going into FOMC ... I cashed these out WAY too early for $1k profit instead of $40k 😭)

Notes: Don't lure yourself into a false sense of security by selling 10-sigma tails. If you feel the need to sell 50X 2 delta puts instead of 5X 20 delta puts, you don't believe in what you or the market is doing.

Example: Being able to take losses is a huge part of this game and VIX explosions should be seen as an opportunity rather than Armageddon. I took a 6-7% drawdown (~$250k) on 12/18 FOMC day where VIX exploded 75%. I realized $75k in losses following my -300% cut rules, added some large batches 45/90 DTE to take advantage of the elevated VIX and was back to ATH within a week while the market still hasn't fully recovered.

VIX Max BPu Max Leverage (SPY Beta Weighted Delta / NLV x SPY)
40+ 50% 2.5X
30-40 40% 2.25X
20-30 35% 2X
15-20 30% 1.75X
10-15 25% 1.5X
Black Swan Hedges

Background: I still have PTSD from 3/12/20.

The Trade: When VIX > $20, buy SPY 7 DTE, 10% OTM puts every week for 0.04% of NLV. When VIX < $20, buy 30 DTE, 20% OTM puts every week for 0.04% of NLV. Also, when VIX < $15, buy 120 DTE, 10 delta VIX calls every month for 0.08% of net liq. Do the math and this is a total of 3%/year portfolio drag.

Management: Hopefully these expire worthless until I'm dead. But if not, I'll only close these for profit if I'm closing other positions for loss. TBH, I'm not entirely sure how I'll manage these when the next 6-sigma event happens, but I know I'll be glad I had them.

Notes: VIX hedge based on Option Alpha YouTube Video. SPY long put hedge based on my own back-testing and stress-testing.

Example: I finally got to use these this year! 8/5 was quite a day so worth documenting the play-by-play here:

Wake up pre-market, see I'm down $400k, and scramble to my computer

See VIX at $65 but remember I have VIX BSH (black swan hedges) that are $300k ITM

Also see my SPY BSH marking pre-market at +3000% and start to feel very confident that I can use this day as an opportunity to make money rather than manage losses

Start by shorting /VX and longing /ES as my BMO move

Cash out the SPY BSH for 20X profits (+$60k)

Cash out one batch of the VIX BSH for 8X profits (+$15k) - sadly VIX dipped well below my strikes before I could cash these out for more

Spent the middle part of the day hunting blue chips for the ridiculous tails on puts and even calls as people were presumably getting liquidated

As the day was wrapping up, closed things at my stops for -$100k and opened large 45/90 DTE short ES put positions for $85k credit

In summary, I thought I handled that all pretty well for my first time. Within a week, my NLV was back to ATH. During the next one, I think I'd avoid straight /ES longs and just short more /VX (or buy SVIX). But I really can't complain as I know many who halved their accounts. And I have heard of some that went negative and are in debt to their broker now.
