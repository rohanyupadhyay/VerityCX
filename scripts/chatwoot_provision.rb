# Provision only this helper's owned account through Chatwoot v4.19.1 ActiveRecord models.
# Execute using `rails runner` inside the pinned image; all output is captured privately.
require 'json'

credentials = JSON.parse(File.read('/run/veritycx/credentials.json'))
owner = credentials.fetch('owner')
callback = 'http://127.0.0.1:8000/integrations/chatwoot/webhook'
result = nil

ActiveRecord::Base.transaction do
  accounts = Account.where("custom_attributes ->> 'veritycx_local_owner' = ?", owner).to_a
  raise 'chatwoot_setup_unowned' if accounts.length > 1

  account = accounts.first
  if account.nil?
    # An empty fresh database is the only allowable first-run target. Never adopt an admin.
    raise 'chatwoot_setup_unowned' if Account.exists? || User.exists? || AgentBot.exists? || Inbox.exists?

    account = Account.create!(name: 'VerityCX synthetic banking', locale: 'en',
                              custom_attributes: { 'veritycx_local_owner' => owner })
    user = User.new(email: credentials.fetch('admin_email'), name: 'VerityCX local administrator',
                    password: credentials.fetch('admin_password'),
                    password_confirmation: credentials.fetch('admin_password'))
    user.skip_confirmation!
    user.save!
    AccountUser.create!(account: account, user: user, role: :administrator)
    channel = Channel::WebWidget.create!(account: account, website_url: 'http://127.0.0.1:8000',
                                        widget_color: '#163c39', welcome_title: 'VerityCX support',
                                        welcome_tagline: 'Synthetic banking demonstration',
                                        continuity_via_email: false, end_conversation: false)
    inbox = Inbox.create!(account: account, channel: channel, name: 'VerityCX website',
                          enable_auto_assignment: false, enable_email_collect: false)
    inbox.add_members([user.id])
    bot = AgentBot.create!(account: account, name: 'VerityCX knowledge assistant',
                           description: "veritycx-local-owner:#{owner}", outgoing_url: callback)
    AgentBotInbox.create!(inbox: inbox, agent_bot: bot, status: :active)
  else
    user = User.find_by!(email: credentials.fetch('admin_email'))
    raise 'chatwoot_admin_changed' unless user.valid_password?(credentials.fetch('admin_password'))
    raise 'chatwoot_setup_unowned' unless account.account_users.exists?(user: user, role: :administrator)
    raise 'chatwoot_setup_unowned' unless account.inboxes.count == 1 && account.agent_bots.count == 1

    inbox = account.inboxes.first!
    bot = account.agent_bots.first!
    raise 'chatwoot_setup_unowned' unless inbox.web_widget? && inbox.name == 'VerityCX website'
    raise 'chatwoot_setup_unowned' unless bot.description == "veritycx-local-owner:#{owner}"
    raise 'chatwoot_setup_unowned' unless bot.outgoing_url == callback && inbox.agent_bot == bot

    # Use the generated flag setter so other existing widget feature flags remain intact.
    inbox.channel.update!(end_conversation: false) if inbox.channel.end_conversation?
  end

  raise 'chatwoot_widget_configuration_invalid' if inbox.channel.reload.end_conversation?

  result = { account_id: account.id, inbox_id: inbox.id, website_token: inbox.channel.website_token,
             api_token: user.access_token.token, bot_token: bot.access_token.token, webhook_secret: bot.secret }
end

# The production seed sets this flag; without clearing it the dashboard stays in public onboarding.
Redis::Alfred.delete(Redis::Alfred::CHATWOOT_INSTALLATION_ONBOARDING)

puts "VERITYCX_RESULT=#{JSON.generate(result)}"
